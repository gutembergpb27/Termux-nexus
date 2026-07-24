"""Nexus Runtime Platform - Core Runtime Engine."""

from __future__ import annotations

from .health import RuntimeHealth
from .state import RuntimeState


class Runtime:
    """Core runtime for the Nexus Runtime Platform."""

    def __init__(self) -> None:
        self._state = RuntimeState.STOPPED
        self.health = RuntimeHealth(self)

    @property
    def started(self) -> bool:
        """Return True when the runtime is running."""
        return self._state is RuntimeState.RUNNING

    @property
    def state(self) -> RuntimeState:
        """Return the current runtime state."""
        return self._state

    def start(self) -> None:
        """Start the runtime."""
        self._state = RuntimeState.STARTING
        self._state = RuntimeState.RUNNING

    def stop(self) -> None:
        """Stop the runtime."""
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED

    def restart(self) -> None:
        """Restart the runtime."""
        self.stop()
        self.start()

    def status(self) -> dict[str, object]:
        """Return runtime status information."""
        return {
            "state": self._state.value,
            "started": self.started,
        }