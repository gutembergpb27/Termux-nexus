"""Scheduler inicial de backends da Nexus Compute."""

from __future__ import annotations

from nexus.compute.registry import BackendRegistry
from nexus.compute.selection import BackendSelection


class BackendScheduler:
    """Seleciona backends disponíveis de forma determinística."""

    def __init__(self, registry: BackendRegistry) -> None:
        self.registry = registry

    def select(self, requested: str) -> BackendSelection:
        name = requested.strip()

        if not name:
            raise ValueError("backend selection must not be empty")

        if name == "auto":
            available = self.registry.names()

            if not available:
                raise RuntimeError("no compute backends available")

            if "local" in available:
                selected = "local"
                reason = "local backend selected by default auto policy"
            else:
                selected = available[0]
                reason = "first available backend selected by auto policy"

            return BackendSelection(
                requested="auto",
                selected=selected,
                reason=reason,
            )

        self.registry.get(name)

        return BackendSelection(
            requested=name,
            selected=name,
            reason="explicit backend selection",
        )
