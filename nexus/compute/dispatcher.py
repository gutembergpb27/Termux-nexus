"""Dispatcher oficial para tarefas distribuídas do Nexus Compute."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from nexus.compute.task import ComputeTask
from nexus.runtime.cluster import RuntimeCluster

NodeExecutor = Callable[[str, ComputeTask], Any]
CapabilityProvider = Callable[[str], Mapping[str, Any]]


class ClusterDispatcher:
    """Resolve um nó compatível e encaminha tarefas ao executor."""

    def __init__(
        self,
        cluster: RuntimeCluster,
        executor: NodeExecutor,
        capabilities: CapabilityProvider | None = None,
    ) -> None:
        self._cluster = cluster
        self._executor = executor
        self._capabilities = capabilities

    def leader(self) -> str:
        """Retorna o líder atual ou falha quando não houver eleição."""

        leader = self._cluster.leader()

        if leader is None:
            raise RuntimeError(
                "cluster leader is not available"
            )

        return leader

    def is_available(self) -> bool:
        """Indica se existe um líder online."""

        leader = self._cluster.leader()

        if leader is None:
            return False

        return leader in self._cluster.online_nodes()

    def _supports(
        self,
        node_id: str,
        handler_name: str,
    ) -> bool:
        provider = self._capabilities

        if provider is None:
            return True

        capabilities = provider(node_id)

        if not isinstance(capabilities, Mapping):
            return False

        handlers = capabilities.get("handlers", ())

        if not isinstance(
            handlers,
            (list, tuple, set, frozenset),
        ):
            return False

        return handler_name in handlers

    def _resolve_target(
        self,
        task: ComputeTask,
        leader: str,
    ) -> str:
        online_nodes = tuple(
            self._cluster.online_nodes()
        )

        if leader not in online_nodes:
            raise RuntimeError(
                "cluster leader is offline"
            )

        # Compatibilidade com o comportamento histórico:
        # sem capability provider, sempre utiliza o líder.
        if self._capabilities is None:
            return leader

        # O líder continua sendo o destino preferencial.
        if self._supports(leader, task.name):
            return leader

        # Caso o líder não suporte a operação, procura
        # deterministicamente outro nó online compatível.
        for node_id in sorted(online_nodes):
            if node_id == leader:
                continue

            if self._supports(
                node_id,
                task.name,
            ):
                return node_id

        raise RuntimeError(
            "no online node supports task handler: "
            f"{task.name}"
        )

    def dispatch(self, task: ComputeTask) -> Any:
        """Encaminha a tarefa a um nó online compatível."""

        leader = self.leader()
        target = self._resolve_target(
            task,
            leader,
        )

        return self._executor(
            target,
            task,
        )

    def __call__(
        self,
        task: ComputeTask,
        leader: str,
    ) -> Any:
        """Mantém compatibilidade com o ClusterBackend."""

        current_leader = self.leader()

        if leader != current_leader:
            raise RuntimeError(
                "stale cluster leader: "
                f"expected {current_leader}, got {leader}"
            )

        target = self._resolve_target(
            task,
            leader,
        )

        return self._executor(
            target,
            task,
        )
