from __future__ import annotations

import pytest

from nexus.compute.task_completion import TaskCompletion


def test_completion_starts_pending() -> None:
    completion = TaskCompletion.pending(
        task_id="task-001",
    )

    assert completion.task_id == "task-001"
    assert completion.status == "pending"
    assert completion.result is None
    assert completion.error is None


def test_completion_can_represent_running() -> None:
    completion = TaskCompletion.running(
        task_id="task-running",
    )

    assert completion.task_id == "task-running"
    assert completion.status == "running"
    assert completion.result is None
    assert completion.error is None


def test_running_completion_rejects_result() -> None:
    with pytest.raises(
        ValueError,
        match="running task must not contain result",
    ):
        TaskCompletion(
            task_id="task-running-result",
            status="running",
            result={"value": 1},
        )


def test_running_completion_rejects_error() -> None:
    with pytest.raises(
        ValueError,
        match="running task must not contain error",
    ):
        TaskCompletion(
            task_id="task-running-error",
            status="running",
            error="boom",
        )


def test_completion_can_represent_success() -> None:
    completion = TaskCompletion.completed(
        task_id="task-002",
        result={"value": 42},
    )

    assert completion.task_id == "task-002"
    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }
    assert completion.error is None


def test_completion_can_represent_failure() -> None:
    completion = TaskCompletion.failed(
        task_id="task-003",
        error="handler failed",
    )

    assert completion.task_id == "task-003"
    assert completion.status == "failed"
    assert completion.result is None
    assert completion.error == "handler failed"


def test_completion_rejects_empty_task_id() -> None:
    with pytest.raises(
        ValueError,
        match="task id",
    ):
        TaskCompletion.pending(
            task_id=" ",
        )


def test_completion_is_immutable() -> None:
    completion = TaskCompletion.pending(
        task_id="task-004",
    )

    with pytest.raises(
        (AttributeError, TypeError),
    ):
        completion.status = "completed"


def test_completion_can_represent_cancellation() -> None:
    completion = TaskCompletion.cancelled(
        task_id="task-cancelled",
    )

    assert completion.task_id == "task-cancelled"
    assert completion.status == "cancelled"
    assert completion.result is None
    assert completion.error is None


def test_cancelled_completion_rejects_result() -> None:
    with pytest.raises(
        ValueError,
        match="cancelled task must not contain result",
    ):
        TaskCompletion(
            task_id="task-cancelled-result",
            status="cancelled",
            result={"value": 1},
        )


def test_cancelled_completion_rejects_error() -> None:
    with pytest.raises(
        ValueError,
        match="cancelled task must not contain error",
    ):
        TaskCompletion(
            task_id="task-cancelled-error",
            status="cancelled",
            error="boom",
        )


def test_cancellation_token_reports_cancelled_state() -> None:
    from nexus.compute.cancellation import CancellationToken
    from nexus.compute.task_completion import TaskCompletionRegistry

    completions = TaskCompletionRegistry()

    completions.create("token-state")

    token = CancellationToken(
        task_id="token-state",
        completions=completions,
    )

    assert token.cancelled is False

    completions.cancel("token-state")

    assert token.cancelled is True


def test_cancellation_token_raises_after_cancel() -> None:
    import pytest

    from nexus.compute.cancellation import (
        CancellationToken,
        TaskCancelledError,
    )
    from nexus.compute.task_completion import TaskCompletionRegistry

    completions = TaskCompletionRegistry()

    completions.create("token-raise")

    token = CancellationToken(
        task_id="token-raise",
        completions=completions,
    )

    completions.cancel("token-raise")

    with pytest.raises(
        TaskCancelledError,
        match="task cancelled",
    ):
        token.raise_if_cancelled()
