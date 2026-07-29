"""Lifecycle facade for the local Nexus Runtime."""

from __future__ import annotations

from nexus.runtime import Runtime


class RuntimeLifecycle:
    """Public lifecycle interface for a local Nexus Runtime."""

    def __init__(self, runtime: Runtime):
        self._runtime = runtime

    @property
    def runtime(self) -> Runtime:
        """Return the underlying Runtime instance."""

        return self._runtime

    @property
    def started(self) -> bool:
        """Return whether the Runtime is running."""

        return self._runtime.started

    def start(self) -> bool:
        """Start the Runtime."""

        return self._runtime.start()

    def stop(self) -> bool:
        """Stop the Runtime."""

        return self._runtime.stop()

    def restart(self) -> bool:
        """Restart the Runtime."""

        return self._runtime.restart()

    def status(self) -> dict[str, object]:
        """Return the Runtime status."""

        return self._runtime.status()
