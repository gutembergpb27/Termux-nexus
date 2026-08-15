from __future__ import annotations

from nexus.compute import (
    ComputeTask,
    TaskQueue,
    build_default_task_registry,
)
from nexus_distributed_core import NexusDistributedCore


def test_core_executes_task_through_queue() -> None:
    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
    )

    result = core.execute_queued_compute_task(task)

    assert result == {"value": 42}
    assert core.compute_task_queue.pending_count() == 0

    load = core.compute_node_load()

    assert load.queued_tasks == 0
    assert load.completed_tasks == 1


def test_handle_compute_task_uses_task_queue() -> None:
    import time

    from nexus_protocol import NexusProtocol, ReplayCache

    class FakeConnection:
        def __init__(self):
            self.payload = None

        def sendall(self, payload):
            self.payload = payload

    core = object.__new__(NexusDistributedCore)
    core.node_id = "NO-QUEUE-01"
    core.protocol = NexusProtocol("test-secret")
    core.compute_replay_cache = ReplayCache()
    core.compute_message_ttl = 60.0
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core.compute_task_completions = TaskCompletionRegistry()
    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    calls = []

    original = core.submit_compute_task

    def tracked(task):
        calls.append(task)
        return original(task)

    core.submit_compute_task = tracked

    message = core.protocol.create_envelope(
        sender="NO-CLIENT-01",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "queue-task-1",
            "name": "echo",
            "task_payload": {
                "value": 42,
            },
        },
        timestamp=time.time(),
        nonce="queue-task-nonce",
        message_id="queue-task-message",
    )

    conn = FakeConnection()

    core.handle_compute_task(
        conn,
        message,
    )

    assert len(calls) == 1
    assert calls[0].name == "echo"
    assert calls[0].payload == {
        "value": 42,
    }


def test_failed_queued_task_leaves_queue_empty() -> None:
    import pytest

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    task = ComputeTask(
        name="data_transform",
        payload={
            "operation": "invalid",
            "values": [1, 2, 3],
        },
    )

    with pytest.raises(
        ValueError,
        match="unsupported data transform operation",
    ):
        core.execute_queued_compute_task(task)

    assert core.compute_task_queue.pending_count() == 0

    load = core.compute_node_load()

    assert load.queued_tasks == 0
    assert load.active_tasks == 0
    assert load.completed_tasks == 0
    assert load.failed_tasks == 1


def test_core_initializes_compute_queue_and_worker(monkeypatch, tmp_path) -> None:
    from nexus.compute import TaskQueue, TaskWorker

    monkeypatch.setenv(
        "NEXUS_SECRET_KEY",
        "test-secret",
    )

    monkeypatch.setenv(
        "NEXUS_DB_PATH",
        str(tmp_path / "nexus-worker.db"),
    )

    monkeypatch.setattr(
        "nexus_distributed_core.start_web_server",
        lambda core, port: None,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.threading.Thread",
        lambda *args, **kwargs: type(
            "FakeThread",
            (),
            {
                "start": lambda self: None,
            },
        )(),
    )

    core = NexusDistributedCore(
        "NO-WORKER-01",
        8081,
        9091,
        "FOLLOWER",
    )

    assert isinstance(
        core.compute_task_queue,
        TaskQueue,
    )

    assert isinstance(
        core.compute_task_worker,
        TaskWorker,
    )


def test_core_initializes_compute_queue_and_worker(monkeypatch, tmp_path) -> None:
    from nexus.compute import TaskQueue, TaskWorker

    monkeypatch.setenv(
        "NEXUS_SECRET_KEY",
        "test-secret",
    )

    monkeypatch.setenv(
        "NEXUS_DB_PATH",
        str(tmp_path / "nexus-worker.db"),
    )

    monkeypatch.setattr(
        "nexus_distributed_core.start_web_server",
        lambda core, port: None,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.threading.Thread",
        lambda *args, **kwargs: type(
            "FakeThread",
            (),
            {
                "start": lambda self: None,
            },
        )(),
    )

    core = NexusDistributedCore(
        "NO-WORKER-01",
        8081,
        9091,
        "FOLLOWER",
    )

    assert isinstance(
        core.compute_task_queue,
        TaskQueue,
    )

    assert isinstance(
        core.compute_task_worker,
        TaskWorker,
    )


def test_core_starts_compute_worker() -> None:
    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    from nexus.compute import TaskWorker

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
    )

    assert core.compute_task_worker.running is False

    assert core.start_compute_worker() is True
    assert core.compute_task_worker.running is True

    assert core.stop_compute_worker(
        timeout=1.0
    ) is True

    assert core.compute_task_worker.running is False


def test_core_compute_worker_start_is_idempotent() -> None:
    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    from nexus.compute import TaskWorker

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
    )

    assert core.start_compute_worker() is True
    assert core.start_compute_worker() is False

    assert core.stop_compute_worker(
        timeout=1.0
    ) is True


def test_core_initializes_completion_registry_with_worker(
    monkeypatch,
    tmp_path,
) -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    monkeypatch.setenv(
        "NEXUS_SECRET_KEY",
        "test-secret",
    )

    monkeypatch.setenv(
        "NEXUS_DB_PATH",
        str(tmp_path / "nexus-completion.db"),
    )

    monkeypatch.setattr(
        "nexus_distributed_core.start_web_server",
        lambda core, port: None,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.threading.Thread",
        lambda *args, **kwargs: type(
            "FakeThread",
            (),
            {
                "start": lambda self: None,
            },
        )(),
    )

    core = NexusDistributedCore(
        "NO-COMPLETION-01",
        8081,
        9091,
        "FOLLOWER",
    )

    assert isinstance(
        core.compute_task_completions,
        TaskCompletionRegistry,
    )


def test_core_creates_completion_for_queued_task() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    from nexus.compute import TaskWorker

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-core-completion-1",
    )

    result = core.execute_queued_compute_task(task)

    assert result == {"value": 42}

    completion = core.compute_task_completions.get(
        "task-core-completion-1"
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }


def test_core_creates_completion_for_queued_task() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    from nexus.compute import TaskWorker

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-core-completion-1",
    )

    result = core.execute_queued_compute_task(task)

    assert result == {"value": 42}

    completion = core.compute_task_completions.get(
        "task-core-completion-1"
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }


def test_core_rejects_duplicate_task_completion_id() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    first = ComputeTask(
        name="echo",
        payload={"value": 1},
        task_id="duplicate-task",
    )

    second = ComputeTask(
        name="echo",
        payload={"value": 2},
        task_id="duplicate-task",
    )

    assert core.execute_queued_compute_task(first) == {
        "value": 1,
    }

    import pytest

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        core.execute_queued_compute_task(second)


def test_core_failed_task_records_failed_completion() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="data_transform",
        payload={
            "operation": "invalid",
            "values": [1, 2, 3],
        },
        task_id="failed-core-task",
    )

    import pytest

    with pytest.raises(
        ValueError,
        match="unsupported data transform operation",
    ):
        core.execute_queued_compute_task(task)

    completion = core.compute_task_completions.get(
        "failed-core-task"
    )

    assert completion is not None
    assert completion.status == "failed"
    assert completion.result is None
    assert (
        "unsupported data transform operation"
        in completion.error
    )


def test_core_waits_for_task_completion_result() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-wait-core-1",
    )

    core.compute_task_completions.create(
        task.task_id
    )

    core.compute_task_queue.enqueue(task)

    assert core.compute_task_worker.start() is True

    completion = core.wait_for_compute_task(
        task.task_id,
        timeout=1.0,
    )

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }

    assert core.compute_task_worker.stop(
        timeout=1.0
    ) is True


def test_core_waits_for_task_completion_result() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-wait-core-1",
    )

    core.compute_task_completions.create(
        task.task_id
    )

    core.compute_task_queue.enqueue(task)

    assert core.compute_task_worker.start() is True

    completion = core.wait_for_compute_task(
        task.task_id,
        timeout=1.0,
    )

    assert completion.status == "completed"
    assert completion.result == {
        "value": 42,
    }

    assert core.compute_task_worker.stop(
        timeout=1.0
    ) is True


def test_core_submits_compute_task_as_pending() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-submit-1",
    )

    completion = core.submit_compute_task(task)

    assert completion.task_id == "task-submit-1"
    assert completion.status == "pending"

    assert core.compute_task_queue.pending_count() == 1

    stored = core.compute_task_completions.get(
        "task-submit-1"
    )

    assert stored == completion


def test_handle_compute_task_uses_submit_and_wait() -> None:
    import time

    from nexus_protocol import NexusProtocol, ReplayCache
    from nexus.compute.task_completion import (
        TaskCompletion,
        TaskCompletionRegistry,
    )
    from nexus.compute import TaskWorker

    class FakeConnection:
        def __init__(self):
            self.payload = None

        def sendall(self, payload):
            self.payload = payload

    core = object.__new__(NexusDistributedCore)
    core.node_id = "NO-COMPLETION-TCP-01"
    core.protocol = NexusProtocol("test-secret")
    core.compute_replay_cache = ReplayCache()
    core.compute_message_ttl = 60.0
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    submitted = []
    waited = []

    def submit(task):
        submitted.append(task)

        return TaskCompletion.pending(
            task_id=task.task_id,
        )

    def wait(task_id, *, timeout=None):
        waited.append(
            (task_id, timeout)
        )

        return TaskCompletion.completed(
            task_id=task_id,
            result={"value": 42},
        )

    core.submit_compute_task = submit
    core.wait_for_compute_task = wait

    message = core.protocol.create_envelope(
        sender="NO-CLIENT-01",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "task-submit-wait-1",
            "name": "echo",
            "task_payload": {
                "value": 42,
            },
        },
        timestamp=time.time(),
        nonce="submit-wait-nonce",
        message_id="submit-wait-message",
    )

    conn = FakeConnection()

    core.handle_compute_task(
        conn,
        message,
    )

    assert len(submitted) == 1
    assert submitted[0].task_id == "task-submit-wait-1"
    assert submitted[0].name == "echo"

    assert waited
    assert waited[0][0] == "task-submit-wait-1"


def test_core_cleans_up_finished_task_completions() -> None:
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_completions = TaskCompletionRegistry()

    core.compute_task_completions.create(
        "task-cleanup-core"
    )
    core.compute_task_completions.complete(
        "task-cleanup-core",
        {"value": 42},
    )

    removed = core.cleanup_compute_completions(
        max_age=0.0,
    )

    assert removed == 1

    assert core.compute_task_completions.get(
        "task-cleanup-core"
    ) is None


def test_core_configures_compute_completion_retention(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "NEXUS_SECRET_KEY",
        "test-secret",
    )

    monkeypatch.setenv(
        "NEXUS_DB_PATH",
        str(tmp_path / "nexus-retention.db"),
    )

    monkeypatch.setenv(
        "NEXUS_COMPLETION_RETENTION_SECONDS",
        "120.0",
    )

    monkeypatch.setattr(
        "nexus_distributed_core.start_web_server",
        lambda core, port: None,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.threading.Thread",
        lambda *args, **kwargs: type(
            "FakeThread",
            (),
            {
                "start": lambda self: None,
            },
        )(),
    )

    core = NexusDistributedCore(
        "NO-RETENTION-01",
        8081,
        9091,
        "FOLLOWER",
    )

    assert (
        core.compute_completion_retention_seconds
        == 120.0
    )


def test_core_rejects_non_positive_completion_retention(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "NEXUS_SECRET_KEY",
        "test-secret",
    )

    monkeypatch.setenv(
        "NEXUS_DB_PATH",
        str(tmp_path / "nexus-retention-invalid.db"),
    )

    monkeypatch.setenv(
        "NEXUS_COMPLETION_RETENTION_SECONDS",
        "0",
    )

    monkeypatch.setattr(
        "nexus_distributed_core.start_web_server",
        lambda core, port: None,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.threading.Thread",
        lambda *args, **kwargs: type(
            "FakeThread",
            (),
            {
                "start": lambda self: None,
            },
        )(),
    )

    import pytest

    with pytest.raises(
        ValueError,
        match="NEXUS_COMPLETION_RETENTION_SECONDS",
    ):
        NexusDistributedCore(
            "NO-RETENTION-BAD",
            8081,
            9091,
            "FOLLOWER",
        )


def test_submit_compute_task_runs_opportunistic_cleanup(
    monkeypatch,
) -> None:
    from nexus.compute import TaskWorker
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()
    core.compute_completion_retention_seconds = 300.0

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    calls = []

    monkeypatch.setattr(
        core,
        "cleanup_compute_completions",
        lambda *, max_age: (
            calls.append(max_age)
            or 0
        ),
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-opportunistic-cleanup",
    )

    completion = core.submit_compute_task(task)

    assert calls == [300.0]

    assert completion.task_id == (
        "task-opportunistic-cleanup"
    )
    assert completion.status == "pending"

    assert core.compute_task_queue.pending_count() == 1


def test_submit_compute_task_runs_opportunistic_cleanup(
    monkeypatch,
) -> None:
    from nexus.compute import TaskWorker
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()
    core.compute_completion_retention_seconds = 300.0

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    calls = []

    monkeypatch.setattr(
        core,
        "cleanup_compute_completions",
        lambda *, max_age: (
            calls.append(max_age)
            or 0
        ),
    )

    task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-opportunistic-cleanup",
    )

    completion = core.submit_compute_task(task)

    assert calls == [300.0]

    assert completion.task_id == (
        "task-opportunistic-cleanup"
    )
    assert completion.status == "pending"

    assert core.compute_task_queue.pending_count() == 1


def test_submit_compute_task_cleans_old_terminal_but_keeps_pending(
    monkeypatch,
) -> None:
    import nexus.compute.task_completion as task_completion_module

    from nexus.compute import TaskWorker
    from nexus.compute.task_completion import (
        TaskCompletionRegistry,
    )

    now = {"value": 100.0}

    monkeypatch.setattr(
        task_completion_module,
        "monotonic",
        lambda: now["value"],
    )

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()
    core.compute_completion_retention_seconds = 5.0

    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )

    core.compute_task_completions.create(
        "task-old-terminal"
    )
    core.compute_task_completions.complete(
        "task-old-terminal",
        {"value": 1},
    )

    core.compute_task_completions.create(
        "task-old-pending"
    )

    now["value"] = 110.0

    new_task = ComputeTask(
        name="echo",
        payload={"value": 42},
        task_id="task-new",
    )

    completion = core.submit_compute_task(
        new_task
    )

    assert core.compute_task_completions.get(
        "task-old-terminal"
    ) is None

    pending = core.compute_task_completions.get(
        "task-old-pending"
    )

    assert pending is not None
    assert pending.status == "pending"

    assert completion.task_id == "task-new"
    assert completion.status == "pending"
