from __future__ import annotations

import pytest

from nexus.compute import ComputeTask, TransportNodeExecutor


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


def test_transport_executor_sends_compute_task(monkeypatch) -> None:
    sent = {}

    task = ComputeTask(
        name="remote-job",
        payload={"value": 42},
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )

    def fake_send_message(conn, message):
        sent["message"] = message

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        fake_send_message,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: {
            "type": "COMPUTE_RESULT",
            "payload": {
                "task_id": task.task_id,
                "status": "completed",
                "node_id": "node-a",
                "output": {"value": 42},
            },
        },
    )

    executor = TransportNodeExecutor(build_peers())

    result = executor("node-a", task)

    assert sent["message"] == {
        "type": "COMPUTE_TASK",
        "payload": {
            "task_id": task.task_id,
            "name": "remote-job",
            "task_payload": {"value": 42},
        },
    }

    assert result == {"value": 42}


def test_transport_executor_rejects_unknown_node() -> None:
    executor = TransportNodeExecutor({})

    with pytest.raises(
        RuntimeError,
        match="unknown cluster node",
    ):
        executor(
            "missing",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_invalid_address() -> None:
    executor = TransportNodeExecutor(
        {
            "node-a": {
                "ip": "",
                "tcp_port": 0,
            }
        }
    )

    with pytest.raises(
        RuntimeError,
        match="invalid cluster node address",
    ):
        executor(
            "node-a",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_invalid_response_type(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: {
            "type": "WRONG",
        },
    )

    executor = TransportNodeExecutor(build_peers())

    with pytest.raises(
        RuntimeError,
        match="invalid compute response type",
    ):
        executor(
            "node-a",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_invalid_response_payload(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: {
            "type": "COMPUTE_RESULT",
            "payload": None,
        },
    )

    executor = TransportNodeExecutor(build_peers())

    with pytest.raises(
        RuntimeError,
        match="invalid compute response payload",
    ):
        executor(
            "node-a",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_task_id_mismatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: {
            "type": "COMPUTE_RESULT",
            "payload": {
                "task_id": "wrong-id",
                "status": "completed",
                "output": None,
            },
        },
    )

    executor = TransportNodeExecutor(build_peers())

    with pytest.raises(
        RuntimeError,
        match="task id mismatch",
    ):
        executor(
            "node-a",
            ComputeTask(name="remote-job"),
        )


def test_transport_executor_rejects_remote_failure(
    monkeypatch,
) -> None:
    task = ComputeTask(name="remote-job")

    monkeypatch.setattr(
        "nexus.compute.transport_executor.socket.create_connection",
        lambda address, timeout: FakeConnection(),
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.send_message",
        lambda conn, message: None,
    )

    monkeypatch.setattr(
        "nexus.compute.transport_executor.recv_message",
        lambda conn: {
            "type": "COMPUTE_RESULT",
            "payload": {
                "task_id": task.task_id,
                "status": "failed",
                "output": None,
            },
        },
    )

    executor = TransportNodeExecutor(build_peers())

    with pytest.raises(
        RuntimeError,
        match="remote compute failed",
    ):
        executor("node-a", task)


def test_transport_executor_rejects_non_positive_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="timeout must be greater than zero",
    ):
        TransportNodeExecutor(
            build_peers(),
            timeout=0,
        )
