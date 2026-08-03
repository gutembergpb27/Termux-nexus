"""Resultado estruturado de uma execução Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ComputeResult:
    """Resultado normalizado retornado por qualquer backend."""

    task_id: str
    backend: str
    status: str
    output: Any
    duration_seconds: float
