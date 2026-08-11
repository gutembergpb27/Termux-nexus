"""Contrato serializável de carga observada de um nó Nexus."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class NodeLoad:
    """Snapshot de carga computacional de um nó do cluster."""

    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        counters = (
            self.active_tasks,
            self.queued_tasks,
            self.completed_tasks,
            self.failed_tasks,
        )

        if any(value < 0 for value in counters):
            raise ValueError(
                "node load counters must be greater than or equal to zero"
            )

        if self.average_duration_ms < 0:
            raise ValueError(
                "average duration must be greater than or equal to zero"
            )

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)
