from __future__ import annotations

import time

import pytest

from nexus_distributed_core import NexusDistributedCore
from nexus.compute import TaskQueue, TaskWorker
from nexus.compute.handlers import build_default_task_registry
from nexus.compute.task_completion import TaskCompletionRegistry
from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache


def build_core():
    core = NexusDistributedCore.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    core.protocol = NexusProtocol("compute-test-secret")
    core.compute_replay_cache = ReplayCache()
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()
    core.compute_task_completions = TaskCompletionRegistry()
    core.compute_task_worker = TaskWorker(
        queue=core.compute_task_queue,
        registry=core.compute_task_handlers,
        completions=core.compute_task_completions,
    )
    core.compute_message_ttl = 60.0
    return core


def make_request(core, *, task_id="task-001"):
    return core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": task_id,
            "name": "echo",
            "task_payload": {"value": 42},
        },
    )


def test_secure_compute_handler_returns_signed_result(
    monkeypatch,
) -> None:
    core = build_core()
    captured = {}

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        lambda conn, message: captured.update(
            message=message
        ),
    )

    core.handle_compute_task(
        object(),
        make_request(core),
    )

    response = captured["message"]

    assert response["type"] == "COMPUTE_RESULT"
    assert response["sender"] == "NODE-A"
    assert "signature" in response
    assert response["payload"]["task_id"] == "task-001"
    assert response["payload"]["status"] == "completed"

    assert core.protocol.verify_envelope(
        response,
        now=time.time(),
        ttl=60.0,
        replay_cache=ReplayCache(),
    )


def test_secure_compute_handler_rejects_tampering(
    monkeypatch,
) -> None:
    core = build_core()
    request = make_request(core)

    request["payload"]["name"] = "tampered"

    with pytest.raises(ProtocolError, match="signature"):
        core.handle_compute_task(object(), request)


def test_secure_compute_handler_rejects_replay(
    monkeypatch,
) -> None:
    core = build_core()
    request = make_request(core)

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        lambda conn, message: None,
    )

    core.handle_compute_task(object(), request)

    with pytest.raises(ProtocolError, match="replay"):
        core.handle_compute_task(object(), request)


def test_dispatch_routes_secure_compute_task(
    monkeypatch,
) -> None:
    core = build_core()
    called = {}

    def fake_handler(conn, message):
        called["message"] = message

    core.handle_compute_task = fake_handler

    message = make_request(core)

    core.dispatch_tcp_message(object(), message)

    assert called["message"] == message


def test_secure_compute_handler_rejects_expired_request(
    monkeypatch,
) -> None:
    core = build_core()

    request = core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "task-expired",
            "name": "echo",
            "task_payload": {},
        },
        timestamp=1000.0,
    )

    monkeypatch.setattr(
        "nexus_distributed_core.time.time",
        lambda: 2000.0,
    )

    with pytest.raises(ProtocolError, match="expired"):
        core.handle_compute_task(object(), request)


def test_secure_compute_handler_rejects_unknown_handler(
    monkeypatch,
) -> None:
    core = build_core()

    request = core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "task-unknown-handler",
            "name": "not_registered",
            "task_payload": {"value": 42},
        },
    )

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        lambda conn, message: None,
    )

    with pytest.raises(
        KeyError,
        match="unknown task handler",
    ):
        core.handle_compute_task(
            object(),
            request,
        )


def test_secure_compute_handler_executes_matrix_multiply(
    monkeypatch,
) -> None:
    core = build_core()
    captured = {}

    request = core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "task-matrix",
            "name": "matrix_multiply",
            "task_payload": {
                "left": [
                    [1, 2],
                    [3, 4],
                ],
                "right": [
                    [5, 6],
                    [7, 8],
                ],
            },
        },
    )

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        lambda conn, message: captured.update(
            message=message
        ),
    )

    core.handle_compute_task(
        object(),
        request,
    )

    response = captured["message"]

    assert response["type"] == "COMPUTE_RESULT"
    assert response["payload"]["task_id"] == "task-matrix"
    assert response["payload"]["status"] == "completed"
    assert response["payload"]["output"] == {
        "matrix": [
            [19, 22],
            [43, 50],
        ],
    }


def test_secure_remote_execution_updates_handler_metrics(
    monkeypatch,
) -> None:
    core = build_core()
    captured = {}

    request = core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": "task-metrics",
            "name": "matrix_multiply",
            "task_payload": {
                "left": [
                    [1, 2],
                    [3, 4],
                ],
                "right": [
                    [5, 6],
                    [7, 8],
                ],
            },
        },
    )

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        lambda conn, message: captured.update(
            message=message
        ),
    )

    before = core.compute_task_handlers.metrics(
        "matrix_multiply"
    )

    assert before.runs == 0

    core.handle_compute_task(
        object(),
        request,
    )

    after = core.compute_task_handlers.metrics(
        "matrix_multiply"
    )

    assert after.runs == 1
    assert after.successes == 1
    assert after.failures == 0
    assert after.last_execution_at is not None
    assert after.last_error is None

    assert captured["message"]["payload"]["output"] == {
        "matrix": [
            [19, 22],
            [43, 50],
        ],
    }
