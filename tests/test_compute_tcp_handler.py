from __future__ import annotations

from nexus_distributed_core import NexusDistributedCore


class FakeConnection:
    def __init__(self) -> None:
        self.sent = b""

    def sendall(self, data: bytes) -> None:
        self.sent += data


def build_core() -> NexusDistributedCore:
    core = NexusDistributedCore.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    return core


def test_compute_task_handler_returns_compute_result(monkeypatch) -> None:
    core = build_core()
    captured = {}

    def fake_send_message(conn, message):
        captured["message"] = message

    monkeypatch.setattr(
        "nexus_distributed_core.send_message",
        fake_send_message,
    )

    core.handle_compute_task(
        FakeConnection(),
        {
            "type": "COMPUTE_TASK",
            "payload": {
                "task_id": "task-001",
                "name": "demo",
                "task_payload": {"value": 42},
            },
        },
    )

    assert captured["message"] == {
        "type": "COMPUTE_RESULT",
        "payload": {
            "task_id": "task-001",
            "status": "completed",
            "node_id": "NODE-A",
            "output": {
                "name": "demo",
                "payload": {"value": 42},
            },
        },
    }


def test_dispatch_tcp_routes_compute_task(monkeypatch) -> None:
    core = build_core()
    called = {}

    def fake_handler(conn, message):
        called["message"] = message

    core.handle_compute_task = fake_handler

    message = {
        "type": "COMPUTE_TASK",
        "payload": {
            "task_id": "task-002",
            "name": "routing",
            "task_payload": {},
        },
    }

    core.dispatch_tcp_message(object(), message)

    assert called["message"] == message
