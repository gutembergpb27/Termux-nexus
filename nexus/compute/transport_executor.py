"""Executor TCP para despacho remoto de tarefas Nexus Compute."""

from __future__ import annotations

import socket
from typing import Any

from nexus.compute.task import ComputeTask
from nexus_transport import recv_message, send_message


class TransportNodeExecutor:
    """Executa tarefas remotas usando o transporte TCP existente."""

    def __init__(
        self,
        peers: dict[str, dict[str, Any]],
        *,
        timeout: float = 3.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self._peers = peers
        self._timeout = float(timeout)

    def _resolve_address(self, node_id: str) -> tuple[str, int]:
        peer = self._peers.get(node_id)

        if peer is None:
            raise RuntimeError(f"unknown cluster node: {node_id}")

        host = str(peer.get("ip", "")).strip()
        tcp_port = int(peer.get("tcp_port", 0))

        if not host or not 1 <= tcp_port <= 65535:
            raise RuntimeError(
                f"invalid cluster node address: {node_id}"
            )

        return host, tcp_port

    def __call__(
        self,
        node_id: str,
        task: ComputeTask,
    ) -> Any:
        host, tcp_port = self._resolve_address(node_id)

        request = {
            "type": "COMPUTE_TASK",
            "payload": {
                "task_id": task.task_id,
                "name": task.name,
                "task_payload": task.payload,
            },
        }

        with socket.create_connection(
            (host, tcp_port),
            timeout=self._timeout,
        ) as conn:
            send_message(conn, request)
            response = recv_message(conn)

        if response.get("type") != "COMPUTE_RESULT":
            raise RuntimeError("invalid compute response type")

        payload = response.get("payload")

        if not isinstance(payload, dict):
            raise RuntimeError(
                "invalid compute response payload"
            )

        if payload.get("task_id") != task.task_id:
            raise RuntimeError(
                "compute response task id mismatch"
            )

        if payload.get("status") != "completed":
            raise RuntimeError(
                f"remote compute failed: {payload.get('status')}"
            )

        return payload.get("output")
