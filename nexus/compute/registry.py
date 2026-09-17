"""Registro de backends da camada Nexus Compute."""

from __future__ import annotations

from nexus.compute.backend import ComputeBackend


class BackendRegistry:
    """Mantém backends disponíveis por nome."""

    def __init__(self) -> None:
        self._backends: dict[str, ComputeBackend] = {}

    def register(self, backend: ComputeBackend) -> None:
        name = backend.name.strip()

        if not name:
            raise ValueError("backend name must not be empty")

        if name in self._backends:
            raise ValueError(f"backend already registered: {name}")

        self._backends[name] = backend

    def get(self, name: str) -> ComputeBackend:
        try:
            return self._backends[name]
        except KeyError as exc:
            raise KeyError(f"unknown backend: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._backends))
