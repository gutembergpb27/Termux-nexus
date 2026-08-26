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
    assert claim.generation == 1
    assert ownership.owner("task-1") == "node-a"

    ownership.release(
        "task-1",
        "node-a",
        claim.generation,
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

    claim = ownership.claim(
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
            claim.generation,
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


def test_task_ownership_generation_increases_after_reclaim() -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "task-generation",
        "node-a",
    )

    ownership.release(
        first.task_id,
        first.node_id,
        first.generation,
    )

    second = ownership.claim(
        "task-generation",
        "node-a",
    )

    assert first.generation == 1
    assert second.generation == 2
    assert second.generation > first.generation


def test_stale_release_cannot_clear_newer_ownership_generation() -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "task-fencing",
        "node-a",
    )

    ownership.release(
        first.task_id,
        first.node_id,
        first.generation,
    )

    second = ownership.claim(
        "task-fencing",
        "node-a",
    )

    with pytest.raises(
        RuntimeError,
        match="stale task ownership generation",
    ):
        ownership.release(
            first.task_id,
            first.node_id,
            first.generation,
        )

    current = ownership.ownership(
        "task-fencing"
    )

    assert current == second

    ownership.release(
        second.task_id,
        second.node_id,
        second.generation,
    )

    assert ownership.owner("task-fencing") is None


def test_stale_generation_is_rejected_even_for_same_node() -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "same-node-generation",
        "node-a",
    )

    ownership.release(
        first.task_id,
        first.node_id,
        first.generation,
    )

    second = ownership.claim(
        "same-node-generation",
        "node-a",
    )

    assert first.node_id == second.node_id
    assert first.generation != second.generation

    with pytest.raises(
        RuntimeError,
        match="stale task ownership generation",
    ):
        ownership.release(
            "same-node-generation",
            "node-a",
            first.generation,
        )

    assert (
        ownership.ownership(
            "same-node-generation"
        )
        == second
    )

def test_registry_reclaims_ownership_from_node_outside_online_membership(
) -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "orphaned-task",
        "node-a",
    )

    reclaimed = ownership.reclaim_orphaned(
        online_nodes={"node-b"},
    )

    assert reclaimed == (first,)
    assert ownership.owner("orphaned-task") is None


def test_registry_preserves_ownership_for_online_owner() -> None:
    ownership = TaskOwnershipRegistry()

    claim = ownership.claim(
        "healthy-owner-task",
        "node-a",
    )

    reclaimed = ownership.reclaim_orphaned(
        online_nodes={"node-a", "node-b"},
    )

    assert reclaimed == ()
    assert (
        ownership.ownership("healthy-owner-task")
        == claim
    )


def test_reclaimed_task_receives_new_generation_on_reassignment(
) -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "reassigned-orphan",
        "node-a",
    )

    reclaimed = ownership.reclaim_orphaned(
        online_nodes={"node-b"},
    )

    assert reclaimed == (first,)

    second = ownership.claim(
        "reassigned-orphan",
        "node-b",
    )

    assert second.node_id == "node-b"
    assert second.generation == first.generation + 1


def test_stale_release_from_reclaimed_generation_is_fenced(
) -> None:
    ownership = TaskOwnershipRegistry()

    first = ownership.claim(
        "reclaimed-fencing",
        "node-a",
    )

    ownership.reclaim_orphaned(
        online_nodes={"node-b"},
    )

    second = ownership.claim(
        "reclaimed-fencing",
        "node-b",
    )

    with pytest.raises(
        RuntimeError,
        match="task ownership mismatch|stale task ownership",
    ):
        ownership.release(
            first.task_id,
            first.node_id,
            first.generation,
        )

    assert (
        ownership.ownership(first.task_id)
        == second
    )


def test_dispatcher_reclaims_orphaned_owner_before_new_dispatch(
) -> None:
    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    orphan = ownership.claim(
        "dispatcher-orphan",
        "node-a",
    )

    assert orphan.generation == 1

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    dispatcher = ClusterDispatcher(
        cluster,
        executor=lambda node_id, task: node_id,
        ownership=ownership,
    )

    task = ComputeTask(
        name="echo",
        task_id="dispatcher-orphan",
    )

    result = dispatcher.dispatch(task)

    assert result == "node-b"
    assert ownership.owner(task.task_id) is None

    # A geração 1 foi revogada; o dispatch por node-b
    # necessariamente utilizou uma geração posterior.
    assert (
        ownership.claim(
            task.task_id,
            "node-b",
        ).generation
        == 3
    )
