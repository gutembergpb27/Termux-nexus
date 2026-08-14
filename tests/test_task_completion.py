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
