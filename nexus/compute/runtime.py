"""Runtime inicial da camada Nexus Compute."""

from __future__ import annotations

from dataclasses import replace

from nexus.compute.local import LocalBackend
from nexus.compute.registry import BackendRegistry
from nexus.compute.result import ComputeResult
from nexus.compute.scheduler import BackendScheduler
from nexus.compute.task import ComputeTask


class ComputeRuntime:
    """Coordena registro, seleção e execução de backends."""

    def __init__(self, registry: BackendRegistry | None = None) -> None:
        self.registry = registry or BackendRegistry()

        if "local" not in self.registry.names():
            self.registry.register(LocalBackend())

        self.scheduler = BackendScheduler(self.registry)

    def run(
        self,
        task: ComputeTask,
        *,
        backend: str = "auto",
    ) -> ComputeResult:
        selection = self.scheduler.select(backend)
        result = self.registry.get(selection.selected).run(task)

        return replace(
            result,
            requested_backend=selection.requested,
            selection_reason=selection.reason,
        )
