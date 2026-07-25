"""Public client for the local Nexus Runtime."""

from __future__ import annotations

from nexus.runtime import Runtime
from nexus.runtime import RuntimeConfig


class RuntimeClient:
    """Stable public interface for a local Nexus Runtime."""

    def __init__(self, config: RuntimeConfig | None = None):
        self._runtime = Runtime(config=config)

    @property
    def runtime(self) -> Runtime:
        """Return the underlying Runtime instance."""

        return self._runtime

    @property
    def config(self) -> RuntimeConfig:
        """Return the Runtime configuration."""

        return self._runtime.config

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
