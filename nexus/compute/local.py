"""Backend local inicial da Nexus Compute."""

from __future__ import annotations

from time import perf_counter

from nexus.compute.backend import ComputeBackend
from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask


class LocalBackend(ComputeBackend):
    """Executa tarefas localmente de forma determinística."""

    name = "local"

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            compute_type="cpu",
            priority=10,
            estimated_latency_ms=1.0,
            estimated_cost=0.0,
            reliability=1.0,
        )

    def run(self, task: ComputeTask) -> ComputeResult:
        started = perf_counter()

        output = {
            "name": task.name,
            "payload": task.payload,
        }

        duration = perf_counter() - started

        return ComputeResult(
            task_id=task.task_id,
            backend=self.name,
            status="completed",
            output=output,
            duration_seconds=duration,
        )
