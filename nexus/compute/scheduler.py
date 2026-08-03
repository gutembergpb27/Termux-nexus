"""Scheduler de backends da Nexus Compute."""

from __future__ import annotations

from nexus.compute.backend import ComputeBackend
from nexus.compute.registry import BackendRegistry
from nexus.compute.selection import BackendSelection


class BackendScheduler:
    """Seleciona backends disponíveis de forma determinística."""

    def __init__(self, registry: BackendRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _ranking_key(
        backend: ComputeBackend,
    ) -> tuple[int, float, float, float, str]:
        capabilities = backend.capabilities()

        return (
            capabilities.priority,
            capabilities.estimated_latency_ms,
            capabilities.estimated_cost,
            -capabilities.reliability,
            backend.name,
        )

    def select(self, requested: str) -> BackendSelection:
        name = requested.strip()

        if not name:
            raise ValueError("backend selection must not be empty")

        if name == "auto":
            candidates = [
                self.registry.get(backend_name)
                for backend_name in self.registry.names()
                if self.registry.get(backend_name).is_available()
            ]

            if not candidates:
                raise RuntimeError("no compute backends available")

            selected_backend = min(candidates, key=self._ranking_key)
            capabilities = selected_backend.capabilities()

            return BackendSelection(
                requested="auto",
                selected=selected_backend.name,
                reason=(
                    "selected by auto policy: "
                    f"priority={capabilities.priority}, "
                    f"latency_ms={capabilities.estimated_latency_ms}, "
                    f"cost={capabilities.estimated_cost}, "
                    f"reliability={capabilities.reliability}"
                ),
            )

        backend = self.registry.get(name)

        if not backend.is_available():
            raise RuntimeError(f"backend unavailable: {name}")

        return BackendSelection(
            requested=name,
            selected=name,
            reason="explicit backend selection",
        )
