"""Runtime diagnostics aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Runtime


class RuntimeDiagnostics:
    """Provide a consolidated diagnostic snapshot for a Runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def snapshot(self) -> dict[str, object]:
        """Return a complete runtime diagnostic snapshot."""

        traces = self._runtime.tracing.history()
        active_traces = sum(
            1
            for trace in traces
            if trace["status"] == "RUNNING"
        )

        return {
            "runtime": self._runtime.status(),
            "health": self._runtime.health.summary(),
            "metrics": self._runtime.metrics.summary(),
            "observability": {
                "events": self._runtime.events.count(),
                "logs": self._runtime.logger.count(),
                "traces": self._runtime.tracing.count(),
                "active_traces": active_traces,
            },
        }

    def summary(self) -> dict[str, object]:
        """Return a compact diagnostic summary."""

        snapshot = self.snapshot()
        runtime = snapshot["runtime"]
        health = snapshot["health"]
        observability = snapshot["observability"]

        if not isinstance(runtime, dict):
            raise TypeError("runtime diagnostics must be a dictionary")

        if not isinstance(health, dict):
            raise TypeError("health diagnostics must be a dictionary")

        if not isinstance(observability, dict):
            raise TypeError(
                "observability diagnostics must be a dictionary"
            )

        return {
            "state": runtime["state"],
            "started": runtime["started"],
            "healthy": health["healthy"],
            "events": observability["events"],
            "logs": observability["logs"],
            "traces": observability["traces"],
            "active_traces": observability["active_traces"],
        }
