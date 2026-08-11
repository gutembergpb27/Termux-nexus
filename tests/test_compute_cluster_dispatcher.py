from __future__ import annotations

import pytest

from nexus.compute import (
    ClusterDispatcher,
    ComputeTask,
)
from nexus.runtime.cluster import RuntimeCluster


def build_cluster_with_leader() -> RuntimeCluster:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")
    return cluster


def test_dispatcher_reports_available_cluster() -> None:
    cluster = build_cluster_with_leader()

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: None,
    )

    assert dispatcher.is_available() is True
    assert dispatcher.leader() == "node-a"


def test_dispatcher_rejects_cluster_without_leader() -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: None,
    )

    assert dispatcher.is_available() is False

    with pytest.raises(
        RuntimeError,
        match="cluster leader is not available",
    ):
        dispatcher.leader()


def test_dispatcher_routes_task_to_current_leader() -> None:
    cluster = build_cluster_with_leader()
    calls: list[tuple[str, str]] = []

    def executor(node_id: str, task: ComputeTask) -> dict[str, str]:
        calls.append((node_id, task.name))
        return {
            "node_id": node_id,
            "task": task.name,
        }

    dispatcher = ClusterDispatcher(cluster, executor=executor)

    result = dispatcher.dispatch(
        ComputeTask(name="distributed-task")
    )

    assert calls == [("node-a", "distributed-task")]
    assert result == {
        "node_id": "node-a",
        "task": "distributed-task",
    }


def test_dispatcher_rejects_stale_leader() -> None:
    cluster = build_cluster_with_leader()

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: None,
    )

    with pytest.raises(
        RuntimeError,
        match="stale cluster leader",
    ):
        dispatcher(
            ComputeTask(name="stale-task"),
            "node-b",
        )


def test_dispatcher_tracks_leader_changes() -> None:
    cluster = build_cluster_with_leader()
    calls: list[str] = []

    def executor(node_id: str, task: ComputeTask) -> str:
        calls.append(node_id)
        return node_id

    dispatcher = ClusterDispatcher(cluster, executor=executor)

    assert dispatcher.dispatch(ComputeTask(name="first")) == "node-a"

    cluster.elect_leader("node-b")

    assert dispatcher.dispatch(ComputeTask(name="second")) == "node-b"

    assert calls == ["node-a", "node-b"]


def test_dispatcher_prefers_capable_leader() -> None:
    cluster = build_cluster_with_leader()
    calls = []

    capabilities = {
        "node-a": {
            "handlers": ["echo", "matrix_multiply"],
        },
        "node-b": {
            "handlers": ["echo"],
        },
    }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: calls.append(node_id) or node_id,
        capabilities=lambda node_id: capabilities.get(
            node_id,
            {"handlers": []},
        ),
    )

    result = dispatcher.dispatch(
        ComputeTask(name="matrix_multiply")
    )

    assert result == "node-a"
    assert calls == ["node-a"]


def test_dispatcher_routes_to_capable_follower_when_leader_cannot_execute() -> None:
    cluster = build_cluster_with_leader()
    calls = []

    capabilities = {
        "node-a": {
            "handlers": ["echo"],
        },
        "node-b": {
            "handlers": ["echo", "matrix_multiply"],
        },
    }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: calls.append(node_id) or node_id,
        capabilities=lambda node_id: capabilities.get(
            node_id,
            {"handlers": []},
        ),
    )

    result = dispatcher.dispatch(
        ComputeTask(name="matrix_multiply")
    )

    assert result == "node-b"
    assert calls == ["node-b"]


def test_dispatcher_rejects_task_when_no_node_advertises_handler() -> None:
    cluster = build_cluster_with_leader()

    capabilities = {
        "node-a": {
            "handlers": ["echo"],
        },
        "node-b": {
            "handlers": ["data_transform"],
        },
    }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: node_id,
        capabilities=lambda node_id: capabilities.get(
            node_id,
            {"handlers": []},
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="no online node supports task handler",
    ):
        dispatcher.dispatch(
            ComputeTask(name="matrix_multiply")
        )


def test_dispatcher_ignores_offline_capable_node() -> None:
    cluster = build_cluster_with_leader()

    capabilities = {
        "node-a": {
            "handlers": ["echo"],
        },
        "node-b": {
            "handlers": ["matrix_multiply"],
        },
    }

    cluster.remove_node("node-b")

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: node_id,
        capabilities=lambda node_id: capabilities.get(
            node_id,
            {"handlers": []},
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="no online node supports task handler",
    ):
        dispatcher.dispatch(
            ComputeTask(name="matrix_multiply")
        )


def test_dispatcher_preserves_leader_only_behavior_without_capabilities_provider() -> None:
    cluster = build_cluster_with_leader()

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: node_id,
    )

    assert dispatcher.dispatch(
        ComputeTask(name="anything")
    ) == "node-a"


def test_dispatcher_uses_peer_capability_provider() -> None:
    from nexus.compute import PeerCapabilityProvider

    cluster = build_cluster_with_leader()
    calls = []

    peers = {
        "node-a": {
            "capabilities": {
                "handlers": ["echo"],
            },
        },
        "node-b": {
            "capabilities": {
                "handlers": [
                    "echo",
                    "matrix_multiply",
                ],
            },
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: (
            calls.append(node_id)
            or node_id
        ),
        capabilities=provider,
    )

    result = dispatcher.dispatch(
        ComputeTask(name="matrix_multiply")
    )

    assert result == "node-b"
    assert calls == ["node-b"]
