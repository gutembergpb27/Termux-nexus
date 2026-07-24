"""Runtime lifecycle states."""

from __future__ import annotations

from enum import Enum


class RuntimeState(str, Enum):
    """Possible lifecycle states of the Nexus Runtime."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"