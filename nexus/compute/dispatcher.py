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

    def _node_capabilities(
        self,
        node_id: str,
    ) -> Mapping[str, Any]:
        provider = self._capabilities

        if provider is None:
            return {}

        capabilities = provider(node_id)

        if not isinstance(capabilities, Mapping):
            return {}

        return capabilities

    def _supports_handler(
        self,
        node_id: str,
        handler_name: str,
    ) -> bool:
        if self._capabilities is None:
            return True

        capabilities = self._node_capabilities(
            node_id
        )

        handlers = capabilities.get(
            "handlers",
            (),
        )

        if not isinstance(
            handlers,
            (list, tuple, set, frozenset),
        ):
            return False

        return handler_name in handlers

    def _satisfies_requirements(
        self,
        node_id: str,
        task: ComputeTask,
    ) -> bool:
        if self._capabilities is None:
            return True

        capabilities = self._node_capabilities(
            node_id
        )
        requirements = task.requirements

        if requirements.compute_type is not None:
            if (
                capabilities.get("compute_type")
                != requirements.compute_type
            ):
                return False

        if requirements.requires_gpu:
            if capabilities.get("has_gpu") is not True:
                return False

        if requirements.min_memory_mb is not None:
            memory_mb = capabilities.get(
                "memory_mb"
            )

            if memory_mb is None:
                return False

            if isinstance(memory_mb, bool):
                return False

            try:
                memory_mb = int(memory_mb)
            except (TypeError, ValueError):
                return False

            if memory_mb < requirements.min_memory_mb:
                return False

        return True

    def _is_eligible(
        self,
        node_id: str,
        task: ComputeTask,
    ) -> bool:
        return (
            self._supports_handler(
                node_id,
                task.name,
            )
            and self._satisfies_requirements(
                node_id,
                task,
            )
        )

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

        # Compatibilidade histórica:
        # sem capability provider, usa o líder.
        if self._capabilities is None:
            return leader

        # Líder continua sendo preferencial quando
        # suporta o handler e satisfaz os requisitos.
        if self._is_eligible(
            leader,
            task,
        ):
            return leader

        # Procura deterministicamente outro nó online.
        for node_id in sorted(online_nodes):
            if node_id == leader:
                continue

            if self._is_eligible(
                node_id,
                task,
            ):
                return node_id

        # Distingue ausência do handler de incapacidade
        # de satisfazer requisitos computacionais.
        handler_available = any(
            self._supports_handler(
                node_id,
                task.name,
            )
            for node_id in online_nodes
        )

        if handler_available:
            raise RuntimeError(
                "no online node satisfies task requirements"
            )

        raise RuntimeError(
            "no online node supports task handler: "
            f"{task.name}"
        )

    def dispatch(self, task: ComputeTask) -> Any:
        """Encaminha a tarefa a um nó online elegível."""

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
