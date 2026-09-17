"""Estado de saúde observado dos backends Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass(frozen=True, slots=True)
class BackendHealth:
    """Representa o estado operacional observado de um backend."""

    available: bool
    status: str
    message: str | None = None
    checked_at: float = field(default_factory=time)

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("health status must not be empty")

        if self.checked_at < 0:
            raise ValueError(
                "health timestamp must be greater than or equal to zero"
            )
