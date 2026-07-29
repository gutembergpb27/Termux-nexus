"""Observability facade for the local Nexus Runtime."""

from __future__ import annotations

from nexus.runtime import Runtime


class RuntimeObservability:
    """Public observability interface for a local Nexus Runtime."""

    def __init__(self, runtime: Runtime):
        self._runtime = runtime

    @property
    def runtime(self) -> Runtime:
        """Return the underlying Runtime instance."""

        return self._runtime

    def health(self) -> dict[str, object]:
        """Return the Runtime health summary."""

        return self._runtime.health.summary()

    def metrics(self) -> dict[str, object]:
        """Return the Runtime metrics summary."""

        return self._runtime.metrics.summary()

    def diagnostics(self) -> dict[str, object]:
        """Return a Runtime diagnostics snapshot."""

        return self._runtime.diagnostics.snapshot()

    def telemetry(self) -> dict[str, object]:
        """Return a Runtime telemetry snapshot."""

        return self._runtime.telemetry.snapshot()

    def snapshot(self) -> dict[str, object]:
        """Return a consolidated observability snapshot."""

        return {
            "health": self.health(),
            "metrics": self.metrics(),
            "diagnostics": self.diagnostics(),
            "telemetry": self.telemetry(),
        }
