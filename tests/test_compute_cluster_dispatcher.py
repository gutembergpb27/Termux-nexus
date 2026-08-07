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
