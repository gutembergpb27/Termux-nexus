"""Scheduler de backends da Nexus Compute."""

from __future__ import annotations

from nexus.compute.backend import ComputeBackend
from nexus.compute.registry import BackendRegistry
from nexus.compute.requirements import ComputeRequirements
from nexus.compute.selection import BackendSelection


class BackendScheduler:
    """Seleciona backends saudáveis, disponíveis e compatíveis."""

    def __init__(self, registry: BackendRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _ranking_key(
        backend: ComputeBackend,
    ) -> tuple[int, int, int, float, float, float, str]:
        capabilities = backend.capabilities()
        metrics = backend.metrics()

        observed_latency = (
            metrics.average_latency_ms
            if metrics.total_runs > 0
            else capabilities.estimated_latency_ms
        )

        return (
            capabilities.priority,
            metrics.active_runs,
            metrics.queued_tasks,
            observed_latency,
            capabilities.estimated_cost,
            -metrics.success_rate,
            backend.name,
        )

    @staticmethod
    def _satisfies(
        backend: ComputeBackend,
        requirements: ComputeRequirements,
    ) -> bool:
        capabilities = backend.capabilities()

        if (
            requirements.compute_type is not None
            and capabilities.compute_type != requirements.compute_type
        ):
            return False

        if requirements.requires_gpu and not capabilities.has_gpu:
            return False

        if requirements.min_memory_mb is not None:
            if capabilities.memory_mb is None:
                return False

            if capabilities.memory_mb < requirements.min_memory_mb:
                return False

        if (
            requirements.max_latency_ms is not None
            and capabilities.estimated_latency_ms
            > requirements.max_latency_ms
        ):
            return False

        if (
            requirements.max_cost is not None
            and capabilities.estimated_cost > requirements.max_cost
        ):
            return False

        if (
            requirements.min_reliability is not None
            and capabilities.reliability
            < requirements.min_reliability
        ):
            return False

        return True

    def select(
        self,
        requested: str,
        *,
        requirements: ComputeRequirements | None = None,
    ) -> BackendSelection:
        name = requested.strip()
        task_requirements = requirements or ComputeRequirements()

        if not name:
            raise ValueError("backend selection must not be empty")

        if name == "auto":
            candidates = []

            for backend_name in self.registry.names():
                backend = self.registry.get(backend_name)
                health = backend.health()

                if not health.available:
                    continue

                if not self._satisfies(backend, task_requirements):
                    continue

                candidates.append(backend)

            if not candidates:
                raise RuntimeError(
                    "no backend satisfies task requirements"
                )

            selected_backend = min(candidates, key=self._ranking_key)
            capabilities = selected_backend.capabilities()
            metrics = selected_backend.metrics()

            observed_latency = (
                metrics.average_latency_ms
                if metrics.total_runs > 0
                else capabilities.estimated_latency_ms
            )

            return BackendSelection(
                requested="auto",
                selected=selected_backend.name,
                reason=(
                    "selected by dynamic auto policy: "
                    f"priority={capabilities.priority}, "
                    f"active_runs={metrics.active_runs}, "
                    f"queued_tasks={metrics.queued_tasks}, "
                    f"latency_ms={observed_latency}, "
                    f"success_rate={metrics.success_rate}"
                ),
            )

        backend = self.registry.get(name)
        health = backend.health()

        if not health.available:
            raise RuntimeError(f"backend unavailable: {name}")

        if not self._satisfies(backend, task_requirements):
            raise RuntimeError(
                f"backend does not satisfy task requirements: {name}"
            )

        return BackendSelection(
            requested=name,
            selected=name,
            reason="explicit backend selection",
        )
