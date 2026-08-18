from __future__ import annotations

import pytest

from nexus.compute import (
    ComputeExecutionObservability,
    ComputeRuntime,
    ComputeTask,
)
from nexus.compute.task_completion import (
    TaskCompletionRegistry,
)


def test_compute_runtime_initializes_completion_registry() -> None:
    runtime = ComputeRuntime()

    assert isinstance(
        runtime.completions,
        TaskCompletionRegistry,
    )


def test_compute_runtime_initializes_execution_observability() -> None:
    runtime = ComputeRuntime()

    assert isinstance(
        runtime.observability,
        ComputeExecutionObservability,
    )

    assert (
        runtime.observability.completions()
        == runtime.completions.snapshot()
    )


def test_compute_runtime_accepts_external_completion_registry() -> None:
    completions = TaskCompletionRegistry()

    runtime = ComputeRuntime(
        completions=completions,
    )

    assert runtime.completions is completions


def test_compute_runtime_records_successful_completion() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-completion-success",
        payload={"value": 42},
    )

    result = runtime.run(task)

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == result
    assert completion.error is None


def test_compute_runtime_records_failed_selection() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-completion-failure",
    )

    with pytest.raises(
        KeyError,
    ):
        runtime.run(
            task,
            backend="missing-backend",
        )

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.result is None
    assert completion.error is not None


def test_compute_runtime_completion_snapshot_reflects_run() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-snapshot",
    )

    runtime.run(task)

    snapshot = runtime.observability.completions()

    assert snapshot.pending == 0
    assert snapshot.running == 0
    assert snapshot.completed == 1
    assert snapshot.failed == 0
    assert snapshot.total == 1


def test_compute_runtime_execution_observability_is_idle_after_run() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-observability",
    )

    runtime.run(task)

    execution = runtime.observability.execution()

    assert execution.running_tasks == 0
    assert execution.long_running_tasks == 0
    assert execution.max_running_elapsed == 0.0


def test_compute_runtime_rejects_duplicate_task_id() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-duplicate",
        task_id="runtime-duplicate-id",
    )

    runtime.run(task)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        runtime.run(task)


def test_compute_runtime_failed_run_is_terminal() -> None:
    runtime = ComputeRuntime()

    task = ComputeTask(
        name="runtime-terminal-failure",
    )

    with pytest.raises(KeyError):
        runtime.run(
            task,
            backend="missing-backend",
        )

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        runtime.run(task)


def test_compute_runtime_cancels_pending_task() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-cancel-pending"
    )

    completion = runtime.cancel(
        "runtime-cancel-pending"
    )

    assert completion.status == "cancelled"

    stored = runtime.completions.get(
        "runtime-cancel-pending"
    )

    assert stored == completion


def test_compute_runtime_cancels_running_task() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-cancel-running"
    )

    runtime.completions.start(
        "runtime-cancel-running"
    )

    completion = runtime.cancel(
        "runtime-cancel-running"
    )

    assert completion.status == "cancelled"


def test_compute_runtime_rejects_unknown_cancellation() -> None:
    runtime = ComputeRuntime()

    import pytest

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        runtime.cancel(
            "runtime-cancel-missing"
        )
