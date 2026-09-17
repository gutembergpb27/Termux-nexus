from __future__ import annotations

import pytest

from nexus.compute import (
    ClusterBackend,
    ClusterDispatcher,
    ComputeRuntime,
    ComputeTask,
    RetryPolicy,
)
from nexus.runtime.cluster import RuntimeCluster


def _build_cluster() -> RuntimeCluster:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")
    return cluster


def _capabilities(node_id: str) -> dict[str, object]:
    return {
        "handlers": ["echo"],
        "compute_type": "cpu",
        "memory_mb": 4096,
        "has_gpu": False,
    }


def test_runtime_retry_recoordinates_after_cluster_leader_change() -> None:
    cluster = _build_cluster()

    calls: list[str] = []

    def executor(
        node_id: str,
        task: ComputeTask,
    ) -> dict[str, str]:
        calls.append(node_id)

        if len(calls) == 1:
            cluster.elect_leader("node-b")
            raise RuntimeError(
                "simulated node-a dispatch failure"
            )

        return {
            "node_id": node_id,
            "task_id": task.task_id,
        }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        capabilities=_capabilities,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="echo",
        task_id="axis2-recoordination-retry",
    )

    result = runtime.run(
        task,
        backend="cluster",
        retry=RetryPolicy(max_attempts=2),
    )

    assert calls == [
        "node-a",
        "node-b",
    ]

    assert result.status == "completed"
    assert result.backend == "cluster"
    assert result.output == {
        "node_id": "node-b",
        "task_id": task.task_id,
    }

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.error is None
    assert completion.result == result

    snapshot = runtime.completions.snapshot()

    assert snapshot.total == 1
    assert snapshot.completed == 1
    assert snapshot.failed == 0


def test_distributed_failure_does_not_recoordinate_without_explicit_retry(
) -> None:
    cluster = _build_cluster()

    calls: list[str] = []

    def executor(
        node_id: str,
        task: ComputeTask,
    ) -> dict[str, str]:
        calls.append(node_id)

        cluster.elect_leader("node-b")

        raise RuntimeError(
            "simulated node-a dispatch failure"
        )

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        capabilities=_capabilities,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="echo",
        task_id="axis2-no-implicit-retry",
    )

    with pytest.raises(
        RuntimeError,
        match="simulated node-a dispatch failure",
    ):
        runtime.run(
            task,
            backend="cluster",
        )

    assert calls == ["node-a"]
    # The cluster may change, but the same execution
    # is not automatically dispatched to the new leader.
    assert cluster.leader() == "node-b"

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"
    assert (
        completion.error
        == "simulated node-a dispatch failure"
    )

    snapshot = runtime.completions.snapshot()

    assert snapshot.total == 1
    assert snapshot.completed == 0
    assert snapshot.failed == 1