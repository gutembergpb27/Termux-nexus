"""Modelos de tarefa para a camada Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from nexus.compute.requirements import ComputeRequirements


@dataclass(frozen=True, slots=True)
class ComputeTask:
    """Representa uma unidade de trabalho independente de backend."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    requirements: ComputeRequirements = field(
        default_factory=ComputeRequirements
    )
    task_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("task name must not be empty")
