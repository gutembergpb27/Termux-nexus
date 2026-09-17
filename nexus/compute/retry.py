"""Explicit retry policy for Nexus Compute execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Define quantas tentativas uma execucao logica pode realizar."""

    max_attempts: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool):
            raise TypeError("max_attempts must be an integer")

        if not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")

        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts must be greater than or equal to 1"
            )
