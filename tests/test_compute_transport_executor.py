from __future__ import annotations

import pytest

from nexus.compute import ComputeTask, TransportNodeExecutor
from nexus_protocol import NexusProtocol, ProtocolError


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def build_peers():
    return {
        "node-a": {
            "ip": "127.0.0.1",
            "tcp_port": 9091,
        }
    }


def build_protocol():
    return NexusProtocol("compute-test-secret")


def build_executor():
    return TransportNodeExecutor(
        build_peers(),
        protocol=build_protocol(),
        sender_id="node-client",
    )


def patch_connection(monkeypatch):
    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )


def test_transport_executor_sends_signed_compute_task(
    monkeypatch,
) -> None:
    sent = {}
    protocol = build_protocol()

    task = ComputeTask(
        name="remote-job",
        payload={"value": 42},
    )

    patch_connection(monkeypatch)

    def fake_send_message(conn, message):
        sent["message"] = message

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        fake_send_message,
    )

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "completed",
            "node_id": "node-a",
            "output": {"value": 42},
        },
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    executor = TransportNodeExecutor(
        build_peers(),
        protocol=protocol,
        sender_id="node-client",
    )

    result = executor("node-a", task)

    request = sent["message"]

    assert request["type"] == "COMPUTE_TASK"
    assert request["sender"] == "node-client"
    assert request["payload"]["task_id"] == task.task_id
    assert request["payload"]["name"] == "remote-job"
    assert "signature" in request

    assert result == {"value": 42}


def test_transport_executor_rejects_tampered_response(
    monkeypatch,
) -> None:
    protocol = build_protocol()
    task = ComputeTask(name="remote-job")

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "completed",
            "output": {"ok": True},
        },
    )

    response["payload"]["status"] = "tampered"

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    executor = TransportNodeExecutor(
        build_peers(),
        protocol=protocol,
        sender_id="node-client",
    )

    with pytest.raises(ProtocolError, match="signature"):
        executor("node-a", task)


def test_transport_executor_rejects_replayed_response(
    monkeypatch,
) -> None:
    protocol = build_protocol()
    task = ComputeTask(name="remote-job")

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "completed",
            "output": {"ok": True},
        },
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    executor = TransportNodeExecutor(
        build_peers(),
        protocol=protocol,
        sender_id="node-client",
    )

    assert executor("node-a", task) == {"ok": True}

    with pytest.raises(ProtocolError, match="replay"):
        executor("node-a", task)


def test_transport_executor_rejects_unknown_node() -> None:
    executor = TransportNodeExecutor(
        {},
        protocol=build_protocol(),
        sender_id="client",
    )

    with pytest.raises(RuntimeError, match="unknown cluster node"):
        executor(
            "missing",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_empty_sender() -> None:
    with pytest.raises(ValueError, match="sender id"):
        TransportNodeExecutor(
            build_peers(),
            protocol=build_protocol(),
            sender_id=" ",
        )


def test_transport_executor_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        TransportNodeExecutor(
            build_peers(),
            protocol=build_protocol(),
            sender_id="client",
            timeout=0,
        )


def test_transport_executor_rejects_non_positive_ttl() -> None:
    with pytest.raises(ValueError, match="message ttl"):
        TransportNodeExecutor(
            build_peers(),
            protocol=build_protocol(),
            sender_id="client",
            message_ttl=0,
        )


def test_transport_executor_rejects_sender_mismatch(
    monkeypatch,
) -> None:
    protocol = build_protocol()
    task = ComputeTask(name="remote-job")

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    response = protocol.create_envelope(
        sender="node-b",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "completed",
            "output": {"ok": True},
        },
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    executor = build_executor()

    with pytest.raises(
        RuntimeError,
        match="sender mismatch",
    ):
        executor("node-a", task)


def test_transport_executor_rejects_expired_response(
    monkeypatch,
) -> None:
    protocol = build_protocol()
    task = ComputeTask(name="remote-job")

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "completed",
            "output": {"ok": True},
        },
        timestamp=1000.0,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.time.time",
        lambda: 2000.0,
    )

    executor = build_executor()

    with pytest.raises(
        ProtocolError,
        match="expired",
    ):
        executor("node-a", task)


def test_transport_executor_raises_on_failed_compute_result(
    monkeypatch,
) -> None:
    task = ComputeTask(
        name="remote-job",
        payload={"value": 42},
        task_id="task-remote-failed",
    )

    protocol = build_protocol()

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "failed",
            "node_id": "node-a",
            "error": "remote handler failed",
        },
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    executor = TransportNodeExecutor(
        build_peers(),
        protocol=protocol,
        sender_id="node-client",
    )

    with pytest.raises(
        RuntimeError,
        match="remote handler failed",
    ):
        executor(
            "node-a",
            task,
        )


def test_transport_executor_raises_timeout_on_timeout_result(
    monkeypatch,
) -> None:
    task = ComputeTask(
        name="remote-job",
        payload={"value": 42},
        task_id="task-remote-timeout",
    )

    protocol = build_protocol()

    response = protocol.create_envelope(
        sender="node-a",
        message_type="COMPUTE_RESULT",
        payload={
            "task_id": task.task_id,
            "status": "timeout",
            "node_id": "node-a",
            "error": "task completion timed out",
        },
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: response,
    )

    patch_connection(monkeypatch)

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    executor = TransportNodeExecutor(
        build_peers(),
        protocol=protocol,
        sender_id="node-client",
    )

    with pytest.raises(
        TimeoutError,
        match="task completion timed out",
    ):
        executor(
            "node-a",
            task,
        )
