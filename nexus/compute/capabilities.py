"""Capacidades declaradas por backends da Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """Descreve propriedades operacionais de um backend."""

    compute_type: str
    priority: int = 100
    estimated_latency_ms: float = 0.0
    estimated_cost: float = 0.0
    reliability: float = 1.0
    memory_mb: int | None = None
    has_gpu: bool = False

    def __post_init__(self) -> None:
        if not self.compute_type.strip():
            raise ValueError("compute type must not be empty")

        if self.priority < 0:
            raise ValueError("priority must be greater than or equal to zero")

        if self.estimated_latency_ms < 0:
            raise ValueError(
                "estimated latency must be greater than or equal to zero"
            )

        if self.estimated_cost < 0:
            raise ValueError(
                "estimated cost must be greater than or equal to zero"
            )

        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be between zero and one")

        if self.memory_mb is not None and self.memory_mb < 0:
            raise ValueError(
                "memory must be greater than or equal to zero"
            )
