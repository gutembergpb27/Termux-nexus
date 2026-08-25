from __future__ import annotations

import pytest

from nexus.compute import (
    ClusterDispatcher,
    ComputeTask,
    TaskOwnershipRegistry,
)
from nexus.runtime.cluster import RuntimeCluster


def test_task_ownership_registry_claims_and_releases_owner() -> None:
    ownership = TaskOwnershipRegistry()

    claim = ownership.claim(
        "task-1",
        "node-a",
    )

    assert claim.task_id == "task-1"
    assert claim.node_id == "node-a"
    assert ownership.owner("task-1") == "node-a"

    ownership.release(
        "task-1",
        "node-a",
    )

    assert ownership.owner("task-1") is None


def test_task_ownership_registry_rejects_duplicate_claim() -> None:
    ownership = TaskOwnershipRegistry()

    ownership.claim(
        "task-1",
        "node-a",
    )

    with pytest.raises(
        RuntimeError,
        match="task already owned",
    ):
        ownership.claim(
            "task-1",
            "node-b",
        )

    assert ownership.owner("task-1") == "node-a"


def test_task_ownership_registry_rejects_release_by_non_owner() -> None:
    ownership = TaskOwnershipRegistry()

    ownership.claim(
        "task-1",
        "node-a",
    )

    with pytest.raises(
        RuntimeError,
        match="task ownership mismatch",
    ):
        ownership.release(
            "task-1",
            "node-b",
        )

    assert ownership.owner("task-1") == "node-a"


def test_dispatcher_exposes_owner_during_execution_and_releases_after_success(
) -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()
    observed: list[str | None] = []

    task = ComputeTask(
        name="echo",
        task_id="owned-success",
    )

    def executor(
        node_id: str,
        current_task: ComputeTask,
    ) -> str:
        observed.append(
            ownership.owner(
                current_task.task_id
            )
        )
        return node_id

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    result = dispatcher.dispatch(task)

    assert result == "node-a"
    assert observed == ["node-a"]
    assert ownership.owner(task.task_id) is None


def test_dispatcher_releases_owner_after_execution_failure() -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    task = ComputeTask(
        name="echo",
        task_id="owned-failure",
    )

    def executor(
        node_id: str,
        current_task: ComputeTask,
    ) -> None:
        assert (
            ownership.owner(
                current_task.task_id
            )
            == "node-a"
        )
        raise RuntimeError(
            "simulated execution failure"
        )

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated execution failure",
    ):
        dispatcher.dispatch(task)

    assert ownership.owner(task.task_id) is None


def test_dispatcher_can_reassign_task_after_previous_owner_releases() -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()
    observed: list[tuple[str, str | None]] = []

    task = ComputeTask(
        name="echo",
        task_id="ownership-reassignment",
    )

    def executor(
        node_id: str,
        current_task: ComputeTask,
    ) -> str:
        observed.append(
            (
                node_id,
                ownership.owner(
                    current_task.task_id
                ),
            )
        )

        if node_id == "node-a":
            raise RuntimeError(
                "simulated first owner failure"
            )

        return node_id

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated first owner failure",
    ):
        dispatcher.dispatch(task)

    assert ownership.owner(task.task_id) is None

    cluster.elect_leader("node-b")

    result = dispatcher.dispatch(task)

    assert result == "node-b"

    assert observed == [
        ("node-a", "node-a"),
        ("node-b", "node-b"),
    ]

    assert ownership.owner(task.task_id) is None