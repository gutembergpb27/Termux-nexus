"""Contrato comum para backends de computação."""

from __future__ import annotations

from abc import ABC, abstractmethod

from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask


class ComputeBackend(ABC):
    """Interface base para mecanismos de execução."""

    name: str

    @abstractmethod
    def run(self, task: ComputeTask) -> ComputeResult:
        """Executa uma tarefa e retorna um resultado normalizado."""
