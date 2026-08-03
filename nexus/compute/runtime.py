"""Runtime inicial da camada Nexus Compute."""

from __future__ import annotations

from nexus.compute.local import LocalBackend
from nexus.compute.registry import BackendRegistry
from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask


class ComputeRuntime:
    """Coordena o registro e a seleção de backends."""

    def __init__(self, registry: BackendRegistry | None = None) -> None:
        self.registry = registry or BackendRegistry()

        if "local" not in self.registry.names():
            self.registry.register(LocalBackend())

    def run(
        self,
        task: ComputeTask,
        *,
        backend: str = "local",
    ) -> ComputeResult:
        return self.registry.get(backend).run(task)
