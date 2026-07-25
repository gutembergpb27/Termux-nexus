"""Runtime telemetry aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Runtime


class RuntimeTelemetry:
    """Provide read-only runtime telemetry."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def snapshot(self) -> dict[str, object]:
        """Return the current runtime telemetry snapshot."""

        return {
            "runtime": {
                "started": self._runtime.started,
                "state": self._runtime.state.value,
            },
            "counters": {
                "events": self._runtime.events.count(),
                "logs": self._runtime.logger.count(),
                "traces": self._runtime.tracing.count(),
            },
        }

    def counters(self) -> dict[str, int]:
        """Return only runtime telemetry counters."""

        return {
            "events": self._runtime.events.count(),
            "logs": self._runtime.logger.count(),
            "traces": self._runtime.tracing.count(),
        }
