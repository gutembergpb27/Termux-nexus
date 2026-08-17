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


def test_registry_marks_pending_task_running() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-1")

    completion = registry.start(
        "task-running-1"
    )

    assert completion == TaskCompletion.running(
        task_id="task-running-1",
    )

    assert registry.get(
        "task-running-1"
    ) == completion


def test_registry_rejects_start_for_unknown_task() -> None:
    registry = TaskCompletionRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        registry.start("missing")


def test_registry_rejects_repeated_start() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-2")
    registry.start("task-running-2")

    with pytest.raises(
        ValueError,
        match="cannot start",
    ):
        registry.start("task-running-2")


def test_registry_completes_running_task() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-3")
    registry.start("task-running-3")

    completion = registry.complete(
        "task-running-3",
        {"value": 42},
    )

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }


def test_registry_fails_running_task() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-4")
    registry.start("task-running-4")

    completion = registry.fail(
        "task-running-4",
        "handler failed",
    )

    assert completion.status == "failed"
    assert completion.error == "handler failed"


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


def test_registry_rejects_repeated_completion() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-terminal-1")

    registry.complete(
        "task-terminal-1",
        {"value": 1},
    )

    with pytest.raises(
        ValueError,
        match="already terminal",
    ):
        registry.complete(
            "task-terminal-1",
            {"value": 2},
        )


def test_registry_rejects_repeated_failure() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-terminal-2")

    registry.fail(
        "task-terminal-2",
        "first failure",
    )

    with pytest.raises(
        ValueError,
        match="already terminal",
    ):
        registry.fail(
            "task-terminal-2",
            "second failure",
        )


def test_registry_rejects_failure_after_completion() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-terminal-3")

    registry.complete(
        "task-terminal-3",
        {"value": 42},
    )

    with pytest.raises(
        ValueError,
        match="already terminal",
    ):
        registry.fail(
            "task-terminal-3",
            "late failure",
        )

    completion = registry.get(
        "task-terminal-3"
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }
    assert completion.error is None


def test_registry_rejects_completion_after_failure() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-terminal-4")

    registry.fail(
        "task-terminal-4",
        "handler failed",
    )

    with pytest.raises(
        ValueError,
        match="already terminal",
    ):
        registry.complete(
            "task-terminal-4",
            {"value": 42},
        )

    completion = registry.get(
        "task-terminal-4"
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.result is None
    assert completion.error == "handler failed"


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


def test_registry_cleanup_removes_old_completed_tasks(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-old-completed")
    registry.complete(
        "task-old-completed",
        {"value": 42},
    )

    now["value"] = 105.0

    removed = registry.cleanup(
        max_age=4.0,
    )

    assert removed == 1
    assert registry.get(
        "task-old-completed"
    ) is None


def test_registry_cleanup_keeps_recent_completed_tasks(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-recent-completed")
    registry.complete(
        "task-recent-completed",
        {"value": 42},
    )

    now["value"] = 103.0

    removed = registry.cleanup(
        max_age=5.0,
    )

    assert removed == 0
    assert registry.get(
        "task-recent-completed"
    ) is not None


def test_registry_cleanup_never_removes_pending_tasks(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()
    registry.create("task-pending")

    now["value"] = 1000.0

    removed = registry.cleanup(
        max_age=1.0,
    )

    assert removed == 0
    assert registry.get(
        "task-pending"
    ) is not None


def test_registry_cleanup_rejects_negative_max_age() -> None:
    registry = TaskCompletionRegistry()

    with pytest.raises(
        ValueError,
        match="max age",
    ):
        registry.cleanup(
            max_age=-1.0,
        )


def test_registry_cleanup_allows_task_id_reuse(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-reusable")
    registry.complete(
        "task-reusable",
        {"value": 1},
    )

    now["value"] = 110.0

    assert registry.cleanup(
        max_age=5.0,
    ) == 1

    recreated = registry.create(
        "task-reusable"
    )

    assert recreated.task_id == "task-reusable"
    assert recreated.status == "pending"
    assert recreated.result is None
    assert recreated.error is None


def test_registry_cleanup_removes_terminal_but_keeps_pending(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-completed")
    registry.complete(
        "task-completed",
        {"value": 1},
    )

    registry.create("task-failed")
    registry.fail(
        "task-failed",
        "boom",
    )

    registry.create("task-pending")

    removed = registry.cleanup(
        max_age=0.0,
    )

    assert removed == 2

    assert registry.get(
        "task-completed"
    ) is None

    assert registry.get(
        "task-failed"
    ) is None

    pending = registry.get(
        "task-pending"
    )

    assert pending is not None
    assert pending.status == "pending"


def test_registry_snapshot_reports_completion_counts() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-pending")

    registry.create("task-completed")
    registry.complete(
        "task-completed",
        {"value": 42},
    )

    registry.create("task-failed")
    registry.fail(
        "task-failed",
        "boom",
    )

    snapshot = registry.snapshot()

    assert snapshot.pending == 1
    assert snapshot.completed == 1
    assert snapshot.failed == 1
    assert snapshot.total == 3


def test_registry_snapshot_is_empty_by_default() -> None:
    registry = TaskCompletionRegistry()

    snapshot = registry.snapshot()

    assert snapshot.pending == 0
    assert snapshot.completed == 0
    assert snapshot.failed == 0
    assert snapshot.total == 0


def test_registry_snapshot_reflects_cleanup(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-pending")

    registry.create("task-completed")
    registry.complete(
        "task-completed",
        {"value": 42},
    )

    registry.create("task-failed")
    registry.fail(
        "task-failed",
        "boom",
    )

    before = registry.snapshot()

    assert before.pending == 1
    assert before.completed == 1
    assert before.failed == 1
    assert before.total == 3

    now["value"] = 110.0

    assert registry.cleanup(
        max_age=5.0,
    ) == 2

    after = registry.snapshot()

    assert after.pending == 1
    assert after.completed == 0
    assert after.failed == 0
    assert after.total == 1


def test_registry_snapshot_reports_running_tasks() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-pending")

    registry.create("task-running")
    registry.start("task-running")

    snapshot = registry.snapshot()

    assert snapshot.pending == 1
    assert snapshot.running == 1
    assert snapshot.completed == 0
    assert snapshot.failed == 0
    assert snapshot.total == 2


def test_registry_snapshot_is_immutable() -> None:
    registry = TaskCompletionRegistry()

    snapshot = registry.snapshot()

    with pytest.raises(
        (AttributeError, TypeError),
    ):
        snapshot.total = 99


def test_registry_wait_does_not_treat_running_as_terminal() -> None:
    import threading
    import time

    registry = TaskCompletionRegistry()

    registry.create("task-running-wait")
    registry.start("task-running-wait")

    def complete_later():
        time.sleep(0.02)
        registry.complete(
            "task-running-wait",
            {"value": 42},
        )

    thread = threading.Thread(
        target=complete_later,
    )
    thread.start()

    completion = registry.wait(
        "task-running-wait",
        timeout=1.0,
    )

    thread.join(timeout=1.0)

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }


def test_registry_wait_times_out_for_running_task() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-timeout")
    registry.start("task-running-timeout")

    with pytest.raises(
        TimeoutError,
        match="task completion timed out",
    ):
        registry.wait(
            "task-running-timeout",
            timeout=0.01,
        )

    completion = registry.get(
        "task-running-timeout"
    )

    assert completion is not None
    assert completion.status == "running"


def test_registry_cleanup_never_removes_running_tasks(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    registry = TaskCompletionRegistry()

    registry.create("task-running-cleanup")
    registry.start("task-running-cleanup")

    now["value"] = 1000.0

    removed = registry.cleanup(
        max_age=1.0,
    )

    assert removed == 0

    completion = registry.get(
        "task-running-cleanup"
    )

    assert completion is not None
    assert completion.status == "running"




def test_registry_running_task_can_reach_only_one_terminal_state() -> None:
    registry = TaskCompletionRegistry()

    registry.create("task-running-terminal")
    registry.start("task-running-terminal")

    completed = registry.complete(
        "task-running-terminal",
        {"value": 1},
    )

    assert completed.status == "completed"

    with pytest.raises(
        ValueError,
        match="already terminal",
    ):
        registry.fail(
            "task-running-terminal",
            "late failure",
        )

    current = registry.get(
        "task-running-terminal"
    )

    assert current == completed
    assert current is not None
    assert current.status == "completed"
    assert current.result == {
        "value": 1,
    }
    assert current.error is None

def test_registry_records_running_start_time(
    monkeypatch,
) -> None:
    registry = TaskCompletionRegistry()

    values = iter([100.0])
    monkeypatch.setattr(
        "nexus.compute.task_completion.monotonic",
        lambda: next(values),
    )

    registry.create("task-start-time")
    registry.start("task-start-time")

    assert registry._started_at["task-start-time"] == 100.0


def test_registry_cleanup_does_not_remove_running_start_time(
    monkeypatch,
) -> None:
    registry = TaskCompletionRegistry()

    values = iter([100.0, 200.0])
    monkeypatch.setattr(
        "nexus.compute.task_completion.monotonic",
        lambda: next(values),
    )

    registry.create("task-running-start")
    registry.start("task-running-start")

    assert registry.cleanup(max_age=0) == 0
    assert registry.get("task-running-start") is not None
    assert registry._started_at["task-running-start"] == 100.0
