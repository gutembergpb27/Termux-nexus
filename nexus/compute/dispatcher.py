"""Dispatcher oficial para tarefas distribuídas do Nexus Compute."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nexus.compute.task import ComputeTask
from nexus.runtime.cluster import RuntimeCluster

NodeExecutor = Callable[[str, ComputeTask], Any]


class ClusterDispatcher:
    """Resolve o líder do cluster e encaminha tarefas ao executor configurado."""

    def __init__(
        self,
        cluster: RuntimeCluster,
        executor: NodeExecutor,
    ) -> None:
        self._cluster = cluster
        self._executor = executor

    def leader(self) -> str:
        """Retorna o líder atual ou falha quando não houver eleição."""

        leader = self._cluster.leader()

        if leader is None:
            raise RuntimeError("cluster leader is not available")

        return leader

    def is_available(self) -> bool:
        """Indica se existe um líder online apto a receber tarefas."""

        leader = self._cluster.leader()

        if leader is None:
            return False

        return leader in self._cluster.online_nodes()

    def dispatch(self, task: ComputeTask) -> Any:
        """Encaminha uma tarefa ao líder atual do cluster."""

        leader = self.leader()

        if leader not in self._cluster.online_nodes():
            raise RuntimeError("cluster leader is offline")

        return self._executor(leader, task)

    def __call__(self, task: ComputeTask, leader: str) -> Any:
        """Mantém compatibilidade com o contrato atual do ClusterBackend."""

        current_leader = self.leader()

        if leader != current_leader:
            raise RuntimeError(
                f"stale cluster leader: expected {current_leader}, got {leader}"
            )

        if leader not in self._cluster.online_nodes():
            raise RuntimeError("cluster leader is offline")

        return self._executor(leader, task)
