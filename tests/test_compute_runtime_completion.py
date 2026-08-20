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


def test_compute_runtime_returns_cancellation_token() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-token"
    )

    token = runtime.cancellation_token(
        "runtime-token"
    )

    assert token.task_id == "runtime-token"
    assert token.cancelled is False


def test_compute_runtime_token_observes_cancellation() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-token-cancel"
    )

    token = runtime.cancellation_token(
        "runtime-token-cancel"
    )

    runtime.cancel(
        "runtime-token-cancel"
    )

    assert token.cancelled is True


def test_compute_runtime_rejects_token_for_unknown_task() -> None:
    import pytest

    runtime = ComputeRuntime()

    with pytest.raises(
        KeyError,
        match="unknown task completion",
    ):
        runtime.cancellation_token(
            "runtime-token-missing"
        )


def test_compute_runtime_token_accepts_deadline() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-deadline"
    )

    token = runtime.cancellation_token(
        "runtime-deadline",
        deadline=123.0,
    )

    assert token.deadline == 123.0


def test_compute_runtime_token_accepts_relative_timeout(
    monkeypatch,
) -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-timeout"
    )

    monkeypatch.setattr(
        "nexus.compute.runtime.monotonic",
        lambda: 100.0,
    )

    token = runtime.cancellation_token(
        "runtime-timeout",
        timeout=5.0,
    )

    assert token.deadline == 105.0


def test_compute_runtime_token_accepts_zero_timeout(
    monkeypatch,
) -> None:
    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-timeout-zero"
    )

    monkeypatch.setattr(
        "nexus.compute.runtime.monotonic",
        lambda: 100.0,
    )

    token = runtime.cancellation_token(
        "runtime-timeout-zero",
        timeout=0.0,
    )

    assert token.deadline == 100.0


def test_compute_runtime_rejects_negative_timeout() -> None:
    import pytest

    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-timeout-negative"
    )

    with pytest.raises(
        ValueError,
        match="timeout must be non-negative",
    ):
        runtime.cancellation_token(
            "runtime-timeout-negative",
            timeout=-1.0,
        )


def test_compute_runtime_rejects_deadline_and_timeout_together() -> None:
    import pytest

    runtime = ComputeRuntime()

    runtime.completions.create(
        "runtime-timeout-conflict"
    )

    with pytest.raises(
        ValueError,
        match="mutually exclusive",
    ):
        runtime.cancellation_token(
            "runtime-timeout-conflict",
            deadline=100.0,
            timeout=5.0,
        )


def test_compute_runtime_health_reports_empty_runtime() -> None:
    runtime = ComputeRuntime()

    health = runtime.health()

    assert health == {
        "healthy": True,
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 0,
    }


def test_compute_runtime_health_reports_task_states() -> None:
    runtime = ComputeRuntime()

    runtime.completions.create("health-pending")

    runtime.completions.create("health-running")
    runtime.completions.start("health-running")

    runtime.completions.create("health-completed")
    runtime.completions.complete(
        "health-completed",
        {"ok": True},
    )

    runtime.completions.create("health-failed")
    runtime.completions.fail(
        "health-failed",
        "boom",
    )

    runtime.completions.create("health-cancelled")
    runtime.completions.cancel(
        "health-cancelled"
    )

    health = runtime.health()

    assert health["healthy"] is True
    assert health["pending"] == 1
    assert health["running"] == 1
    assert health["completed"] == 1
    assert health["failed"] == 1
    assert health["cancelled"] == 1
    assert health["total"] == 5


def test_compute_runtime_starts_empty_without_completion_store() -> None:
    runtime = ComputeRuntime()

    assert runtime.completions.snapshot().total == 0


def test_compute_runtime_recovers_completions_from_store(
    tmp_path,
) -> None:
    from nexus.compute import TaskCompletionStore
    from nexus.compute.task_completion import TaskCompletionRegistry

    path = tmp_path / "runtime-state.json"

    registry = TaskCompletionRegistry()

    registry.create("recovered-pending")

    registry.create("recovered-completed")
    registry.complete(
        "recovered-completed",
        {"value": 42},
    )

    store = TaskCompletionStore(path)

    store.save(registry)

    runtime = ComputeRuntime(
        completion_store=store,
    )

    assert (
        runtime.completions.get(
            "recovered-pending"
        ).status
        == "pending"
    )

    completed = runtime.completions.get(
        "recovered-completed"
    )

    assert completed.status == "completed"
    assert completed.result == {
        "value": 42
    }


def test_compute_runtime_recovery_marks_running_as_failed(
    tmp_path,
) -> None:
    from nexus.compute import TaskCompletionStore
    from nexus.compute.task_completion import TaskCompletionRegistry

    path = tmp_path / "runtime-running.json"

    registry = TaskCompletionRegistry()

    registry.create("recovered-running")
    registry.start("recovered-running")

    store = TaskCompletionStore(path)
    store.save(registry)

    runtime = ComputeRuntime(
        completion_store=store,
    )

    completion = runtime.completions.get(
        "recovered-running"
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.error == (
        "task interrupted by runtime restart"
    )


def test_compute_runtime_missing_store_file_starts_empty(
    tmp_path,
) -> None:
    from nexus.compute import TaskCompletionStore

    store = TaskCompletionStore(
        tmp_path / "missing-runtime.json"
    )

    runtime = ComputeRuntime(
        completion_store=store,
    )

    assert runtime.completions.snapshot().total == 0


def test_compute_runtime_rejects_corrupt_store_on_startup(
    tmp_path,
) -> None:
    import pytest

    from nexus.compute import TaskCompletionStore

    path = tmp_path / "corrupt-runtime.json"

    path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    store = TaskCompletionStore(path)

    with pytest.raises(
        ValueError,
        match="invalid task completion state JSON",
    ):
        ComputeRuntime(
            completion_store=store,
        )


def test_compute_runtime_persist_saves_current_state(
    tmp_path,
) -> None:
    from nexus.compute import TaskCompletionStore

    path = tmp_path / "persist-runtime.json"

    store = TaskCompletionStore(path)

    runtime = ComputeRuntime(
        completion_store=store,
    )

    runtime.completions.create(
        "persisted-task"
    )

    runtime.persist()

    recovered = ComputeRuntime(
        completion_store=store,
    )

    assert recovered.completions.get(
        "persisted-task"
    ).status == "pending"


def test_compute_runtime_persist_requires_store() -> None:
    import pytest

    runtime = ComputeRuntime()

    with pytest.raises(
        RuntimeError,
        match="completion store is not configured",
    ):
        runtime.persist()


def test_compute_runtime_health_reflects_recovered_state(
    tmp_path,
) -> None:
    from nexus.compute import TaskCompletionStore
    from nexus.compute.task_completion import TaskCompletionRegistry

    path = tmp_path / "health-recovery.json"

    registry = TaskCompletionRegistry()

    registry.create("health-recovered")

    store = TaskCompletionStore(path)
    store.save(registry)

    runtime = ComputeRuntime(
        completion_store=store,
    )

    health = runtime.health()

    assert health["healthy"] is True
    assert health["pending"] == 1
    assert health["total"] == 1

def test_compute_runtime_auto_persists_successful_run(
    tmp_path,
) -> None:
    from nexus.compute import (
        ComputeRuntime,
        ComputeTask,
        TaskCompletionStore,
    )

    path = tmp_path / "auto-persist-success.json"

    runtime = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    task = ComputeTask(
        name="auto-persist-success",
        payload={"value": 42},
    )

    result = runtime.run(task)

    assert path.exists()

    recovered = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    completion = recovered.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"

    assert completion.result == {
        "task_id": result.task_id,
        "backend": result.backend,
        "status": result.status,
        "output": result.output,
        "duration_seconds": result.duration_seconds,
        "requested_backend": result.requested_backend,
        "selection_reason": result.selection_reason,
    }

def test_compute_runtime_auto_persists_failed_run(
    tmp_path,
) -> None:
    from nexus.compute import (
        ComputeRuntime,
        ComputeTask,
        TaskCompletionStore,
    )

    path = tmp_path / "auto-persist-failed.json"

    runtime = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    task = ComputeTask(
        name="auto-persist-failed",
    )

    try:
        runtime.run(
            task,
            backend="missing-backend",
        )
    except KeyError:
        pass
    else:
        raise AssertionError(
            "expected backend selection failure"
        )

    assert path.exists()

    recovered = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    completion = recovered.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.error is not None


def test_compute_runtime_auto_persists_cancelled_task(
    tmp_path,
) -> None:
    from nexus.compute import (
        ComputeRuntime,
        TaskCompletionStore,
    )

    path = tmp_path / "auto-persist-cancelled.json"

    runtime = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    runtime.completions.create(
        "auto-persist-cancelled"
    )

    runtime.cancel(
        "auto-persist-cancelled"
    )

    assert path.exists()

    recovered = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    completion = recovered.completions.get(
        "auto-persist-cancelled"
    )

    assert completion is not None
    assert completion.status == "cancelled"

def test_compute_runtime_auto_persists_transition_sequence(
    tmp_path,
    monkeypatch,
) -> None:
    from nexus.compute import (
        ComputeRuntime,
        ComputeTask,
        TaskCompletionStore,
    )

    path = tmp_path / "auto-persist-sequence.json"

    store = TaskCompletionStore(path)

    observed_statuses = []

    original_save = store.save

    def recording_save(registry) -> None:
        completion = next(
            iter(
                registry.export_state()["items"]
            )
        )

        observed_statuses.append(
            completion["status"]
        )

        original_save(registry)

    monkeypatch.setattr(
        store,
        "save",
        recording_save,
    )

    runtime = ComputeRuntime(
        completion_store=store,
    )

    task = ComputeTask(
        name="auto-persist-sequence",
        payload={"value": 42},
    )

    runtime.run(task)

    assert observed_statuses == [
        "pending",
        "running",
        "completed",
    ]

    recovered = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    completion = recovered.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"


def test_retry_policy_defaults_to_single_attempt() -> None:
    from nexus.compute import RetryPolicy

    policy = RetryPolicy()

    assert policy.max_attempts == 1


def test_retry_policy_rejects_zero_attempts() -> None:
    from nexus.compute import RetryPolicy

    with pytest.raises(
        ValueError,
        match="greater than or equal to 1",
    ):
        RetryPolicy(max_attempts=0)


def test_retry_policy_rejects_boolean_attempts() -> None:
    from nexus.compute import RetryPolicy

    with pytest.raises(
        TypeError,
        match="must be an integer",
    ):
        RetryPolicy(max_attempts=True)


def test_compute_runtime_retry_succeeds_before_limit() -> None:
    from nexus.compute import RetryPolicy
    from nexus.compute.backend import ComputeBackend
    from nexus.compute.capabilities import BackendCapabilities
    from nexus.compute.result import ComputeResult

    class FlakyBackend(ComputeBackend):
        name = "flaky"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(compute_type="cpu")

        def run(self, task):
            self.calls += 1

            if self.calls < 3:
                raise RuntimeError("transient failure")

            return ComputeResult(
                task_id=task.task_id,
                backend=self.name,
                status="completed",
                output={"attempt": self.calls},
                duration_seconds=0.0,
            )

    backend = FlakyBackend()

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="runtime-retry-success",
    )

    result = runtime.run(
        task,
        backend="flaky",
        retry=RetryPolicy(max_attempts=3),
    )

    assert backend.calls == 3
    assert result.output == {"attempt": 3}

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == result


def test_compute_runtime_retry_fails_only_after_limit() -> None:
    from nexus.compute import RetryPolicy
    from nexus.compute.backend import ComputeBackend
    from nexus.compute.capabilities import BackendCapabilities

    class AlwaysFailingBackend(ComputeBackend):
        name = "always-failing"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(compute_type="cpu")

        def run(self, task):
            self.calls += 1
            raise RuntimeError("persistent failure")

    backend = AlwaysFailingBackend()

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="runtime-retry-failure",
    )

    with pytest.raises(
        RuntimeError,
        match="persistent failure",
    ):
        runtime.run(
            task,
            backend="always-failing",
            retry=RetryPolicy(max_attempts=3),
        )

    assert backend.calls == 3

    completion = runtime.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.error == "persistent failure"


def test_compute_runtime_default_retry_preserves_single_attempt() -> None:
    from nexus.compute.backend import ComputeBackend
    from nexus.compute.capabilities import BackendCapabilities

    class FailingBackend(ComputeBackend):
        name = "single-attempt"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(compute_type="cpu")

        def run(self, task):
            self.calls += 1
            raise RuntimeError("single failure")

    backend = FailingBackend()

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="runtime-default-retry",
    )

    with pytest.raises(
        RuntimeError,
        match="single failure",
    ):
        runtime.run(
            task,
            backend="single-attempt",
        )

    assert backend.calls == 1


def test_compute_runtime_retry_keeps_single_logical_completion() -> None:
    from nexus.compute import RetryPolicy
    from nexus.compute.backend import ComputeBackend
    from nexus.compute.capabilities import BackendCapabilities
    from nexus.compute.result import ComputeResult

    class RetryBackend(ComputeBackend):
        name = "retry-idempotency"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(compute_type="cpu")

        def run(self, task):
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError("retry once")

            return ComputeResult(
                task_id=task.task_id,
                backend=self.name,
                status="completed",
                output={"ok": True},
                duration_seconds=0.0,
            )

    backend = RetryBackend()

    runtime = ComputeRuntime(
        additional_backends=(backend,),
    )

    task = ComputeTask(
        name="runtime-retry-idempotency",
        task_id="retry-single-logical-completion",
    )

    runtime.run(
        task,
        backend="retry-idempotency",
        retry=RetryPolicy(max_attempts=2),
    )

    snapshot = runtime.completions.snapshot()

    assert backend.calls == 2
    assert snapshot.total == 1
    assert snapshot.completed == 1
    assert snapshot.failed == 0


def test_compute_runtime_retry_persists_only_terminal_failure_after_exhaustion(
    tmp_path,
) -> None:
    from nexus.compute import (
        RetryPolicy,
        TaskCompletionStore,
    )
    from nexus.compute.backend import ComputeBackend
    from nexus.compute.capabilities import BackendCapabilities

    class PersistFailBackend(ComputeBackend):
        name = "persist-retry-failure"

        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(compute_type="cpu")

        def run(self, task):
            self.calls += 1
            raise RuntimeError("retry exhausted")

    backend = PersistFailBackend()
    path = tmp_path / "retry-failure.json"

    runtime = ComputeRuntime(
        additional_backends=(backend,),
        completion_store=TaskCompletionStore(path),
    )

    task = ComputeTask(
        name="runtime-retry-persist-failure",
    )

    with pytest.raises(
        RuntimeError,
        match="retry exhausted",
    ):
        runtime.run(
            task,
            backend="persist-retry-failure",
            retry=RetryPolicy(max_attempts=2),
        )

    assert backend.calls == 2

    recovered = ComputeRuntime(
        completion_store=TaskCompletionStore(path),
    )

    completion = recovered.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.error == "retry exhausted"