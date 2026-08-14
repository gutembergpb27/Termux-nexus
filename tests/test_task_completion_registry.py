from __future__ import annotations

import pytest

from nexus.compute.task_completion import (
    TaskCompletion,
    TaskCompletionRegistry,
)


def test_registry_creates_pending_completion() -> None:
    registry = TaskCompletionRegistry()

    completion = registry.create(
        "task-001",
    )

    assert completion == TaskCompletion.pending(
        task_id="task-001",
    )

    assert registry.get("task-001") == completion


def test_registry_rejects_duplicate_task_id() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-001")

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        registry.create("task-001")


def test_registry_marks_task_completed() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-002")

    completion = registry.complete(
        "task-002",
        {"value": 42},
    )

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }
    assert completion.error is None

    assert registry.get("task-002") == completion


def test_registry_marks_task_failed() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-003")

    completion = registry.fail(
        "task-003",
        "handler failed",
    )

    assert completion.status == "failed"
    assert completion.result is None
    assert completion.error == "handler failed"

    assert registry.get("task-003") == completion


def test_registry_returns_none_for_unknown_task() -> None:
    registry = TaskCompletionRegistry()

    assert registry.get("missing") is None


def test_registry_rejects_completion_for_unknown_task() -> None:
    registry = TaskCompletionRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        registry.complete(
            "missing",
            {"value": 1},
        )


def test_registry_rejects_failure_for_unknown_task() -> None:
    registry = TaskCompletionRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        registry.fail(
            "missing",
            "boom",
        )


def test_registry_wait_returns_completed_task() -> None:
    import threading
    import time

    registry = TaskCompletionRegistry()
    registry.create("task-wait-1")

    def complete_later():
        time.sleep(0.02)
        registry.complete(
            "task-wait-1",
            {"value": 42},
        )

    thread = threading.Thread(
        target=complete_later,
    )
    thread.start()

    completion = registry.wait(
        "task-wait-1",
        timeout=1.0,
    )

    thread.join(timeout=1.0)

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }


def test_registry_wait_returns_failed_task() -> None:
    import threading
    import time

    registry = TaskCompletionRegistry()
    registry.create("task-wait-2")

    def fail_later():
        time.sleep(0.02)
        registry.fail(
            "task-wait-2",
            "boom",
        )

    thread = threading.Thread(
        target=fail_later,
    )
    thread.start()

    completion = registry.wait(
        "task-wait-2",
        timeout=1.0,
    )

    thread.join(timeout=1.0)

    assert completion.status == "failed"
    assert completion.error == "boom"


def test_registry_wait_times_out_for_pending_task() -> None:
    registry = TaskCompletionRegistry()
    registry.create("task-wait-3")

    with pytest.raises(
        TimeoutError,
        match="task completion timed out",
    ):
        registry.wait(
            "task-wait-3",
            timeout=0.01,
        )


def test_registry_wait_rejects_unknown_task() -> None:
    registry = TaskCompletionRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        registry.wait(
            "missing",
            timeout=0.01,
        )
