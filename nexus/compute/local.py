"""Backend local inicial da Nexus Compute."""

from __future__ import annotations

from time import perf_counter

from nexus.compute.backend import ComputeBackend
from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.health import BackendHealth
from nexus.compute.metrics import BackendMetrics
from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask


class LocalBackend(ComputeBackend):
    """Executa tarefas localmente e registra métricas dinâmicas."""

    name = "local"

    def __init__(self) -> None:
        self._completed_runs = 0
        self._failed_runs = 0
        self._active_runs = 0
        self._total_duration_seconds = 0.0

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            compute_type="cpu",
            priority=10,
            estimated_latency_ms=1.0,
            estimated_cost=0.0,
            reliability=1.0,
            memory_mb=None,
            has_gpu=False,
        )

    def health(self) -> BackendHealth:
        return BackendHealth(
            available=True,
            status="healthy",
            message="local backend operational",
        )

    def metrics(self) -> BackendMetrics:
        return BackendMetrics(
            completed_runs=self._completed_runs,
            failed_runs=self._failed_runs,
            active_runs=self._active_runs,
            queued_tasks=0,
            total_duration_seconds=self._total_duration_seconds,
        )

    def run(self, task: ComputeTask) -> ComputeResult:
        started = perf_counter()
        self._active_runs += 1

        try:
            output = {
                "name": task.name,
                "payload": task.payload,
            }

            result = ComputeResult(
                task_id=task.task_id,
                backend=self.name,
                status="completed",
                output=output,
                duration_seconds=perf_counter() - started,
            )

            self._completed_runs += 1
            return result
        except Exception:
            self._failed_runs += 1
            raise
        finally:
            duration = perf_counter() - started
            self._total_duration_seconds += duration
            self._active_runs -= 1
