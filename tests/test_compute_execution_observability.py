from __future__ import annotations

import pytest

from nexus.compute import ComputeExecutionObservability
from nexus.compute.task_completion import TaskCompletionRegistry


def test_compute_execution_observability_exposes_execution_snapshot(
    monkeypatch,
) -> None:
    registry = TaskCompletionRegistry()

    clock = {"value": 100.0}

    monkeypatch.setattr(
        "nexus.compute.task_completion.monotonic",
        lambda: clock["value"],
    )

    registry.create("task-running")
    registry.start("task-running")

    clock["value"] = 145.0

    observability = ComputeExecutionObservability(
        registry
    )

    execution = observability.execution(
        max_elapsed=30.0,
    )

    assert execution.running_tasks == 1
    assert execution.long_running_tasks == 1
    assert execution.max_running_elapsed == 45.0


def test_compute_execution_observability_preserves_exact_threshold(
    monkeypatch,
) -> None:
    registry = TaskCompletionRegistry()

    clock = {"value": 50.0}

    monkeypatch.setattr(
        "nexus.compute.task_completion.monotonic",
        lambda: clock["value"],
    )

    registry.create("task-boundary")
    registry.start("task-boundary")

    clock["value"] = 60.0

    observability = ComputeExecutionObservability(
        registry
    )

    execution = observability.execution(
        max_elapsed=10.0,
    )

    assert execution.running_tasks == 1
    assert execution.long_running_tasks == 0
    assert execution.max_running_elapsed == 10.0


def test_compute_execution_observability_rejects_negative_threshold(
) -> None:
    registry = TaskCompletionRegistry()

    observability = ComputeExecutionObservability(
        registry
    )

    with pytest.raises(
        ValueError,
        match="max_elapsed must be non-negative",
    ):
        observability.execution(
            max_elapsed=-1.0,
        )


def test_compute_execution_observability_exposes_completion_snapshot(
) -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-completed")
    registry.complete(
        "task-completed",
        {"value": 42},
    )

    observability = ComputeExecutionObservability(
        registry
    )

    completions = observability.completions()

    assert completions.pending == 0
    assert completions.running == 0
    assert completions.completed == 1
    assert completions.failed == 0
    assert completions.total == 1


def test_compute_execution_observability_snapshot_is_consolidated(
) -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-pending")

    observability = ComputeExecutionObservability(
        registry
    )

    snapshot = observability.snapshot(
        max_elapsed=30.0,
    )

    assert set(snapshot) == {
        "execution",
        "completions",
    }

    assert snapshot["execution"].running_tasks == 0
    assert snapshot["execution"].long_running_tasks == 0
    assert snapshot["execution"].max_running_elapsed == 0.0

    assert snapshot["completions"].pending == 1
    assert snapshot["completions"].running == 0
    assert snapshot["completions"].completed == 0
    assert snapshot["completions"].failed == 0
    assert snapshot["completions"].total == 1


def test_compute_execution_observability_default_threshold(
    monkeypatch,
) -> None:
    registry = TaskCompletionRegistry()

    clock = {"value": 100.0}

    monkeypatch.setattr(
        "nexus.compute.task_completion.monotonic",
        lambda: clock["value"],
    )

    registry.create("task-default-threshold")
    registry.start("task-default-threshold")

    clock["value"] = 131.0

    observability = ComputeExecutionObservability(
        registry
    )

    execution = observability.execution()

    assert execution.running_tasks == 1
    assert execution.long_running_tasks == 1
    assert execution.max_running_elapsed == 31.0


def test_compute_execution_observability_public_import() -> None:
    from nexus.compute import ComputeExecutionObservability as PublicFacade

    assert PublicFacade is ComputeExecutionObservability
