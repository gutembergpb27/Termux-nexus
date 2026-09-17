from __future__ import annotations

from threading import Event, Thread

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
def test_stale_execution_cannot_produce_protected_side_effect():
    cluster = RuntimeCluster()

    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    task = ComputeTask(
        task_id="stale-side-effect-contract",
        name="side-effect",
    )

    first_started = Event()
    allow_first_finish = Event()

    effects = []
    errors = {}

    def executor(node_id, current_task):
        if node_id == "node-a":
            first_started.set()

            if not allow_first_finish.wait(timeout=5):
                raise RuntimeError(
                    "timeout waiting for recoordination"
                )

            dispatcher.assert_execution_current(
                current_task.task_id,
                node_id,
            )

            effects.append(
                (
                    "STALE_EFFECT",
                    node_id,
                    current_task.task_id,
                )
            )

            return "stale"

        effects.append(
            (
                "CURRENT_EFFECT",
                node_id,
                current_task.task_id,
            )
        )

        return "current"

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    def first_run():
        try:
            dispatcher.dispatch(task)
        except Exception as exc:
            errors["first"] = exc

    thread = Thread(target=first_run)
    thread.start()

    if not first_started.wait(timeout=5):
        raise AssertionError(
            "generation #1 did not start"
        )

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    second_result = dispatcher.dispatch(task)

    allow_first_finish.set()

    thread.join(timeout=5)

    if thread.is_alive():
        raise AssertionError(
            "generation #1 did not finish"
        )

    assert second_result == "current"

    assert any(
        effect[0] == "CURRENT_EFFECT"
        for effect in effects
    )

    # CONTRATO 6:
    #
    # Depois da perda de ownership, a execucao stale
    # nao deve conseguir produzir um efeito protegido.
    #
    # Hoje esta assercao falha, materializando o gap.

    assert not any(
        effect[0] == "STALE_EFFECT"
        for effect in effects
    )


def test_terminal_state_converges_after_ownership_recoordination():
    from threading import Event, Thread

    from nexus.compute import (
        ClusterBackend,
        ClusterDispatcher,
        ComputeRuntime,
        ComputeTask,
        TaskOwnershipRegistry,
    )
    from nexus.runtime.cluster import RuntimeCluster

    task_id = "terminal-state-convergence-contract"

    cluster = RuntimeCluster()

    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    first_started = Event()
    allow_first_finish = Event()

    def executor(node_id, task):
        if node_id == "node-a":
            first_started.set()

            if not allow_first_finish.wait(timeout=5):
                raise RuntimeError(
                    "timeout waiting for recoordination"
                )

            return {
                "winner": "stale",
                "node": node_id,
            }

        return {
            "winner": "current",
            "node": node_id,
        }

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    runtime_a = ComputeRuntime(
        additional_backends=(backend,),
    )

    runtime_b = ComputeRuntime(
        additional_backends=(backend,),
    )

    task_a = ComputeTask(
        task_id=task_id,
        name="terminal-state-convergence",
    )

    task_b = ComputeTask(
        task_id=task_id,
        name="terminal-state-convergence",
    )

    old_error = {}

    def run_old_generation():
        try:
            runtime_a.run(
                task_a,
                backend="cluster",
            )
        except Exception as exc:
            old_error["error"] = exc

    thread = Thread(
        target=run_old_generation,
        name="terminal-state-old-generation",
    )

    thread.start()

    if not first_started.wait(timeout=5):
        raise AssertionError(
            "old generation did not start"
        )

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    current_result = runtime_b.run(
        task_b,
        backend="cluster",
    )

    allow_first_finish.set()

    thread.join(timeout=5)

    if thread.is_alive():
        raise AssertionError(
            "old generation did not finish"
        )

    old_completion = runtime_a.completions.get(
        task_id
    )

    current_completion = runtime_b.completions.get(
        task_id
    )

    assert current_result.status == "completed"

    assert current_completion is not None
    assert current_completion.status == "completed"

    assert old_completion is not None

    # CONTRATO 7:
    #
    # A geracao stale nao deve produzir uma decisao terminal
    # concorrente que contradiga a decisao terminal vencedora.
    #
    # A decisao autoritativa para este task_id e "completed".
    #
    # Hoje o runtime antigo termina como "failed",
    # materializando divergencia terminal distribuida.

    assert old_completion.status == "completed"

    assert old_completion.result == current_completion.result

def test_terminal_failure_converges_after_ownership_recoordination():
    from threading import Event, Thread

    from nexus.compute import (
        ClusterBackend,
        ClusterDispatcher,
        ComputeRuntime,
        ComputeTask,
        TaskOwnershipRegistry,
    )
    from nexus.runtime.cluster import RuntimeCluster

    task_id = "terminal-failure-convergence-contract"

    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    first_started = Event()
    allow_first_finish = Event()

    def executor(node_id, task):
        if node_id == "node-a":
            first_started.set()

            if not allow_first_finish.wait(timeout=5):
                raise RuntimeError(
                    "timeout waiting for failure recoordination"
                )

            return {
                "winner": "stale",
                "node": node_id,
            }

        raise RuntimeError("authoritative terminal failure")

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    runtime_a = ComputeRuntime(
        additional_backends=(backend,),
    )

    runtime_b = ComputeRuntime(
        additional_backends=(backend,),
    )

    task_a = ComputeTask(
        task_id=task_id,
        name="terminal-failure-convergence",
    )

    task_b = ComputeTask(
        task_id=task_id,
        name="terminal-failure-convergence",
    )

    old_error = {}
    current_error = {}

    def run_old_generation():
        try:
            runtime_a.run(
                task_a,
                backend="cluster",
            )
        except Exception as exc:
            old_error["error"] = exc

    thread = Thread(
        target=run_old_generation,
        name="terminal-failure-old-generation",
    )

    thread.start()

    if not first_started.wait(timeout=5):
        raise AssertionError(
            "old generation did not start"
        )

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    try:
        runtime_b.run(
            task_b,
            backend="cluster",
        )
    except Exception as exc:
        current_error["error"] = exc

    allow_first_finish.set()

    thread.join(timeout=5)

    if thread.is_alive():
        raise AssertionError(
            "old generation did not finish"
        )

    old_completion = runtime_a.completions.get(
        task_id
    )

    current_completion = runtime_b.completions.get(
        task_id
    )

    assert "error" in current_error

    assert current_completion is not None
    assert current_completion.status == "failed"
    assert (
        current_completion.error
        == "authoritative terminal failure"
    )

    assert old_completion is not None

    # CONTRATO 8:
    #
    # Depois que a geracao atual estabelece uma falha
    # terminal autoritativa, a geracao stale nao pode
    # materializar uma causa terminal concorrente.
    #
    # As duas visoes devem convergir para a mesma
    # decisao terminal.

    assert old_completion.status == "failed"
    assert old_completion.error == current_completion.error


def test_stale_generation_cannot_publish_failure_before_authoritative_failure():
    from threading import Event, Thread

    from nexus.compute import (
        ClusterBackend,
        ClusterDispatcher,
        ComputeRuntime,
        ComputeTask,
        TaskOwnershipRegistry,
    )
    from nexus.runtime.cluster import RuntimeCluster

    task_id = "terminal-failure-stale-first-contract"

    cluster = RuntimeCluster()
    cluster.add_node("node-a")
    cluster.add_node("node-b")
    cluster.elect_leader("node-a")

    ownership = TaskOwnershipRegistry()

    old_started = Event()
    allow_old_finish = Event()

    current_started = Event()
    allow_current_failure = Event()

    def executor(node_id, task):
        if node_id == "node-a":
            old_started.set()

            if not allow_old_finish.wait(timeout=5):
                raise RuntimeError(
                    "timeout waiting to finish stale generation"
                )

            return {
                "winner": "stale",
                "node": node_id,
            }

        current_started.set()

        if not allow_current_failure.wait(timeout=5):
            raise RuntimeError(
                "timeout waiting for authoritative failure"
            )

        raise RuntimeError(
            "authoritative terminal failure"
        )

    dispatcher = ClusterDispatcher(
        cluster,
        executor=executor,
        ownership=ownership,
    )

    backend = ClusterBackend(
        cluster,
        dispatcher=dispatcher,
    )

    runtime_a = ComputeRuntime(
        additional_backends=(backend,),
    )

    runtime_b = ComputeRuntime(
        additional_backends=(backend,),
    )

    task_a = ComputeTask(
        task_id=task_id,
        name="terminal-failure-stale-first",
    )

    task_b = ComputeTask(
        task_id=task_id,
        name="terminal-failure-stale-first",
    )

    old_error = {}
    current_error = {}

    def run_old_generation():
        try:
            runtime_a.run(
                task_a,
                backend="cluster",
            )
        except Exception as exc:
            old_error["error"] = exc

    def run_current_generation():
        try:
            runtime_b.run(
                task_b,
                backend="cluster",
            )
        except Exception as exc:
            current_error["error"] = exc

    old_thread = Thread(
        target=run_old_generation,
        name="terminal-failure-stale-first-old",
    )

    old_thread.start()

    if not old_started.wait(timeout=5):
        raise AssertionError(
            "old generation did not start"
        )

    cluster.remove_node("node-a")
    cluster.elect_leader("node-b")

    current_thread = Thread(
        target=run_current_generation,
        name="terminal-failure-stale-first-current",
    )

    current_thread.start()

    if not current_started.wait(timeout=5):
        raise AssertionError(
            "current generation did not start"
        )

    # --------------------------------------------------------
    # CRITICAL ORDER:
    #
    # stale generation finishes BEFORE the current generation
    # publishes its authoritative terminal failure.
    # --------------------------------------------------------

    allow_old_finish.set()

    old_thread.join(timeout=5)

    if old_thread.is_alive():
        raise AssertionError(
            "old generation did not finish"
        )

    old_completion_before_authority = (
        runtime_a.completions.get(task_id)
    )

    assert old_completion_before_authority is not None

    # A stale generation may locally observe loss of authority,
    # but that observation must NOT become the cluster's
    # authoritative terminal failure.

    allow_current_failure.set()

    current_thread.join(timeout=5)

    if current_thread.is_alive():
        raise AssertionError(
            "current generation did not finish"
        )

    current_completion = runtime_b.completions.get(
        task_id
    )

    old_completion = runtime_a.completions.get(
        task_id
    )

    assert "error" in current_error

    assert current_completion is not None
    assert current_completion.status == "failed"

    # The current generation owns the terminal decision.

    assert (
        current_completion.error
        == "authoritative terminal failure"
    )

    # The stale generation must not have poisoned the shared
    # terminal authority with its StaleTaskOwnershipError.

    assert old_completion is not None

    authoritative_failure = backend._terminal_failure(
        task_id
    )

    assert (
        authoritative_failure
        == "authoritative terminal failure"
    )

    # Contract 8 convergence:
    #
    # no competing stale ownership error can become the
    # authoritative cluster terminal cause.

    assert (
        "task is not owned"
        not in authoritative_failure
    )
