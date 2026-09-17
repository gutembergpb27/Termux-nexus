"""Métricas dinâmicas dos backends Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendMetrics:
    """Snapshot das métricas observadas de um backend."""

    completed_runs: int = 0
    failed_runs: int = 0
    active_runs: int = 0
    queued_tasks: int = 0
    total_duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        counters = (
            self.completed_runs,
            self.failed_runs,
            self.active_runs,
            self.queued_tasks,
        )

        if any(value < 0 for value in counters):
            raise ValueError(
                "backend metric counters must be greater than or equal to zero"
            )

        if self.total_duration_seconds < 0:
            raise ValueError(
                "total duration must be greater than or equal to zero"
            )

    @property
    def total_runs(self) -> int:
        return self.completed_runs + self.failed_runs

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 1.0

        return self.completed_runs / self.total_runs

    @property
    def average_latency_ms(self) -> float:
        if self.total_runs == 0:
            return 0.0

        return (
            self.total_duration_seconds
            / self.total_runs
            * 1000.0
        )
