"""Seleção estruturada de backend para a Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendSelection:
    """Registra a decisão tomada pelo scheduler."""

    requested: str
    selected: str
    reason: str
