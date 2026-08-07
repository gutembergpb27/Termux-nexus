from __future__ import annotations

import time

import pytest

from nexus_distributed_core import NexusDistributedCore
from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache


def build_core():
    core = NexusDistributedCore.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    core.protocol = NexusProtocol("compute-test-secret")
    core.compute_replay_cache = ReplayCache()
    core.compute_message_ttl = 60.0
    return core


def make_request(core, *, task_id="task-001"):
    return core.protocol.create_envelope(
        sender="NODE-B",
        message_type="COMPUTE_TASK",
        payload={
            "task_id": task_id,
            "name": "demo",
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
            "name": "demo",
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
