"""Requisitos formais de uma tarefa da Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComputeRequirements:
    """Define restrições usadas na seleção de backends."""

    compute_type: str | None = None
    min_memory_mb: int | None = None
    requires_gpu: bool = False
    max_latency_ms: float | None = None
    max_cost: float | None = None
    min_reliability: float | None = None

    def __post_init__(self) -> None:
        if self.compute_type is not None and not self.compute_type.strip():
            raise ValueError("compute type must not be empty")

        if self.min_memory_mb is not None and self.min_memory_mb < 0:
            raise ValueError(
                "minimum memory must be greater than or equal to zero"
            )

        if self.max_latency_ms is not None and self.max_latency_ms < 0:
            raise ValueError(
                "maximum latency must be greater than or equal to zero"
            )

        if self.max_cost is not None and self.max_cost < 0:
            raise ValueError(
                "maximum cost must be greater than or equal to zero"
            )

        if (
            self.min_reliability is not None
            and not 0.0 <= self.min_reliability <= 1.0
        ):
            raise ValueError(
                "minimum reliability must be between zero and one"
            )
