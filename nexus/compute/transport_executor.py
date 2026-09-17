"""Executor TCP autenticado para tarefas remotas Nexus Compute."""

from __future__ import annotations

import socket
import time
from typing import Any

from nexus.compute.task import ComputeTask
from nexus_protocol import NexusProtocol, ReplayCache
from nexus_transport import recv_message, send_message


class TransportNodeExecutor:
    """Executa tarefas remotas usando o protocolo seguro do Nexus."""

    def __init__(
        self,
        peers: dict[str, dict[str, Any]],
        *,
        protocol: NexusProtocol,
        sender_id: str,
        timeout: float = 3.0,
        message_ttl: float = 60.0,
        replay_cache: ReplayCache | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if message_ttl <= 0:
            raise ValueError(
                "message ttl must be greater than zero"
            )

        sender = sender_id.strip()

        if not sender:
            raise ValueError("sender id must not be empty")

        self._peers = peers
        self._protocol = protocol
        self._sender_id = sender
        self._timeout = float(timeout)
        self._message_ttl = float(message_ttl)
        self._replay_cache = replay_cache or ReplayCache()

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

        request = self._protocol.create_envelope(
            sender=self._sender_id,
            message_type="COMPUTE_TASK",
            payload={
                "task_id": task.task_id,
                "name": task.name,
                "task_payload": task.payload,
            },
        )

        with socket.create_connection(
            (host, tcp_port),
            timeout=self._timeout,
        ) as conn:
            send_message(conn, request)
            response = recv_message(conn)

        self._protocol.verify_envelope(
            response,
            now=time.time(),
            ttl=self._message_ttl,
            replay_cache=self._replay_cache,
        )

        if response.get("type") != "COMPUTE_RESULT":
            raise RuntimeError("invalid compute response type")

        if response.get("sender") != node_id:
            raise RuntimeError(
                "compute response sender mismatch"
            )

        payload = response.get("payload")

        if not isinstance(payload, dict):
            raise RuntimeError(
                "invalid compute response payload"
            )

        if payload.get("task_id") != task.task_id:
            raise RuntimeError(
                "compute response task id mismatch"
            )

        status = payload.get("status")

        if status == "failed":
            error = str(
                payload.get("error")
                or "remote compute failed"
            )

            raise RuntimeError(error)

        if status == "timeout":
            error = str(
                payload.get("error")
                or "remote compute timed out"
            )

            raise TimeoutError(error)

        if status != "completed":
            raise RuntimeError(
                f"remote compute failed: {status}"
            )

        return payload.get("output")
