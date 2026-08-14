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

    calls = []

    original = core.execute_queued_compute_task

    def tracked(task):
        calls.append(task)
        return original(task)

    core.execute_queued_compute_task = tracked

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
