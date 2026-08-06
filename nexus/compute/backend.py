"""Contrato comum para backends de computação."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.health import BackendHealth
from nexus.compute.metrics import BackendMetrics
from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask


class ComputeBackend(ABC):
    """Interface base para mecanismos de execução."""

    name: str

    @abstractmethod
    def run(self, task: ComputeTask) -> ComputeResult:
        """Executa uma tarefa e retorna um resultado normalizado."""

    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Retorna as capacidades declaradas pelo backend."""

    def is_available(self) -> bool:
        """Indica se o backend pode receber tarefas."""

        return True

    def health(self) -> BackendHealth:
        """Retorna o estado operacional atual do backend."""

        available = self.is_available()

        return BackendHealth(
            available=available,
            status="healthy" if available else "unavailable",
        )

    def metrics(self) -> BackendMetrics:
        """Retorna métricas observadas do backend."""

        return BackendMetrics()
