"""Public client for the local Nexus Runtime."""

from __future__ import annotations

from nexus.runtime import Runtime
from nexus.runtime import RuntimeConfig
from nexus.runtime_observability import RuntimeObservability


class RuntimeClient:
    """Stable public interface for a local Nexus Runtime."""

    def __init__(self, config: RuntimeConfig | None = None):
        self._runtime = Runtime(config=config)
        self._observability = RuntimeObservability(self._runtime)

    @property
    def runtime(self) -> Runtime:
        """Return the underlying Runtime instance."""

        return self._runtime

    @property
    def config(self) -> RuntimeConfig:
        """Return the Runtime configuration."""

        return self._runtime.config

    @property
    def cluster(self):
        """Return the Runtime cluster facade."""

        return self._runtime.cluster

    @property
    def observability(self) -> RuntimeObservability:
        """Return the Runtime observability facade."""

        return self._observability

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

        return self._observability.health()

    def metrics(self) -> dict[str, object]:
        """Return the Runtime metrics summary."""

        return self._observability.metrics()

    def diagnostics(self) -> dict[str, object]:
        """Return a Runtime diagnostics snapshot."""

        return self._observability.diagnostics()

    def telemetry(self) -> dict[str, object]:
        """Return a Runtime telemetry snapshot."""

        return self._observability.telemetry()
