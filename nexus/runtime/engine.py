"""Nexus Runtime Platform - Core Runtime Engine."""

from __future__ import annotations


class Runtime:
    """Core runtime for the Nexus Runtime Platform."""

    def __init__(self) -> None:
        self._started = False

    @property
    def started(self) -> bool:
        """Return whether the runtime has been started."""
        return self._started

    def start(self) -> None:
        """Start the runtime."""
        self._started = True

    def stop(self) -> None:
        """Stop the runtime."""
        self._started = False