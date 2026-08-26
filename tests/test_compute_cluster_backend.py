from __future__ import annotations

import pytest

from nexus.compute import (
    ClusterDispatcher,
    ClusterBackend,
    ComputeRequirements,
    ComputeRuntime,
    ComputeTask,
    TaskOwnershipRegistry,
)
from nexus.runtime.cluster import RuntimeCluster


def build_cluster_with_leader() -> RuntimeCluster:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")
    return cluster


def test_cluster_backend_is_unavailable_without_dispatcher() -> None:
    cluster = build_cluster_with_leader()
    backend = ClusterBackend(cluster)

    health = backend.health()

    assert health.available is False
    assert health.status == "unavailable"
    assert health.message == "cluster dispatcher is not configured"


def test_cluster_backend_is_degraded_without_leader() -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")

    backend = ClusterBackend(
        cluster,
        dispatcher=lambda task, leader: None,
    )

    health = backend.health()

    assert health.available is False
    assert health.status == "degraded"
    assert health.message == "cluster leader is not elected"


def test_cluster_backend_reports_healthy() -> None:
    cluster = build_cluster_with_leader()

    backend = ClusterBackend(
        cluster,
        dispatcher=lambda task, leader: None,
    )

    health = backend.health()

    assert health.available is True
    assert health.status == "healthy"
    assert health.message == "cluster backend operational"


def test_cluster_backend_dispatches_to_leader() -> None:
    cluster = build_cluster_with_leader()
    calls: list[tuple[str, str]] = []

    def dispatcher(task: ComputeTask, leader: str) -> dict[str, str]:
        calls.append((task.name, leader))
        return {
            "task": task.name,
            "leader": leader,
        }

    backend = ClusterBackend(cluster, dispatcher=dispatcher)
    task = ComputeTask(name="distributed-job")

    result = backend.run(task)

    assert calls == [("distributed-job", "node-a")]
    assert result.backend == "cluster"
    assert result.status == "completed"
    assert result.output == {
        "task": "distributed-job",
        "leader": "node-a",
    }


def test_cluster_backend_updates_metrics() -> None:
    cluster = build_cluster_with_leader()

    backend = ClusterBackend(
        cluster,
        dispatcher=lambda task, leader: {"accepted": True},
    )

    before = backend.metrics()
    backend.run(ComputeTask(name="metrics-job"))
    after = backend.metrics()

    assert before.completed_runs == 0
    assert after.completed_runs == 1
    assert after.failed_runs == 0
    assert after.active_runs == 0
    assert after.total_duration_seconds >= 0


def test_cluster_backend_records_dispatch_failure() -> None:
    cluster = build_cluster_with_leader()

    def failing_dispatcher(
        task: ComputeTask,
        leader: str,
    ) -> None:
        raise RuntimeError("dispatch failed")

    backend = ClusterBackend(
        cluster,
        dispatcher=failing_dispatcher,
    )

    with pytest.raises(RuntimeError, match="dispatch failed"):
        backend.run(ComputeTask(name="failure-job"))

    metrics = backend.metrics()

    assert metrics.completed_runs == 0
    assert metrics.failed_runs == 1
    assert metrics.active_runs == 0


def test_compute_runtime_registers_cluster_backend() -> None:
    cluster = build_cluster_with_leader()

    backend = ClusterBackend(
        cluster,
        dispatcher=lambda task, leader: {
            "leader": leader,
            "payload": task.payload,
        },
    )

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    assert runtime.registry.names() == ("cluster", "local")


def test_runtime_selects_cluster_for_cluster_requirement() -> None:
    cluster = build_cluster_with_leader()

    backend = ClusterBackend(
        cluster,
        dispatcher=lambda task, leader: {
            "leader": leader,
        },
    )

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="cluster-job",
        requirements=ComputeRequirements(
            compute_type="cluster",
        ),
    )

    result = runtime.run(task)

    assert result.backend == "cluster"
    assert result.requested_backend == "auto"
    assert result.output == {"leader": "node-a"}


def test_cluster_backend_routes_to_capable_follower() -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    calls = []

    capabilities = {
        "node-a": {
            "handlers": ["echo"],
        },
        "node-b": {
            "handlers": [
                "echo",
                "matrix_multiply",
            ],
        },
    }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: (
            calls.append(node_id)
            or {
                "node_id": node_id,
                "task": task.name,
            }
        ),
        capabilities=lambda node_id: capabilities.get(
            node_id,
            {"handlers": []},
        ),
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    result = backend.run(
        ComputeTask(
            name="matrix_multiply",
            payload={
                "left": [[1]],
                "right": [[2]],
            },
        )
    )

    assert calls == ["node-b"]

    assert result.backend == "cluster"
    assert result.status == "completed"
    assert result.output == {
        "node_id": "node-b",
        "task": "matrix_multiply",
    }


def test_cluster_backend_reclaims_orphaned_ownership_before_dispatch(
) -> None:
    cluster = RuntimeCluster()

    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    orphan = ownership.claim(
        "backend-orphaned-task",
        "node-a",
    )

    assert orphan.generation == 1

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    executions: list[tuple[str, str]] = []

    def executor(
        node_id: str,
        task: ComputeTask,
    ) -> dict[str, str]:
        executions.append(
            (node_id, task.task_id)
        )

        return {
            "node": node_id,
            "task": task.task_id,
        }

    dispatcher = ClusterDispatcher(
        cluster,
        executor,
        ownership=ownership,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    task = ComputeTask(
        task_id="backend-orphaned-task",
        name="demo",
    )

    result = backend.run(task)

    assert result.status == "completed"
    assert result.output == {
        "node": "node-b",
        "task": "backend-orphaned-task",
    }

    assert executions == [
        ("node-b", "backend-orphaned-task"),
    ]

    assert ownership.owner(task.task_id) is None

    next_claim = ownership.claim(
        task.task_id,
        "node-b",
    )

    assert next_claim.generation == 3
