"""Runtime engine."""

from __future__ import annotations

from nexus.runtime.cluster import RuntimeCluster
from nexus.runtime.config import RuntimeConfig
from nexus.runtime.diagnostics import RuntimeDiagnostics
from nexus.runtime.events import RuntimeEvents
from nexus.runtime.health import RuntimeHealth
from nexus.runtime.logger import RuntimeLogger
from nexus.runtime.metrics import RuntimeMetrics
from nexus.runtime.state import RuntimeState
from nexus.runtime.telemetry import RuntimeTelemetry
from nexus.runtime.tracing import RuntimeTracing


class Runtime:
    """Main Runtime API."""

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()
        self._state = RuntimeState.STOPPED

        self.health = RuntimeHealth(self)
        self.cluster = RuntimeCluster()
        self.metrics = RuntimeMetrics(self)
        self.events = RuntimeEvents()
        self.logger = RuntimeLogger()
        self.tracing = RuntimeTracing()
        self.diagnostics = RuntimeDiagnostics(self)
        self.telemetry = RuntimeTelemetry(self)

    @property
    def started(self) -> bool:
        return self._state == RuntimeState.RUNNING

    @property
    def state(self) -> RuntimeState:
        return self._state

    def start(self):
        if self._state == RuntimeState.RUNNING:
            return False

        trace = self.tracing.begin("runtime.start")

        self._state = RuntimeState.STARTING
        self.logger.info("Runtime starting")

        self._state = RuntimeState.RUNNING

        self.events.publish("runtime.started")
        self.logger.info("Runtime started")
        self.tracing.finish(trace["trace_id"])

        return True

    def stop(self):
        if self._state == RuntimeState.STOPPED:
            return False

        trace = self.tracing.begin("runtime.stop")

        self._state = RuntimeState.STOPPING

        self.events.publish("runtime.stopping")
        self.logger.info("Runtime stopping")

        self._state = RuntimeState.STOPPED

        self.events.publish("runtime.stopped")
        self.logger.info("Runtime stopped")
        self.tracing.finish(trace["trace_id"])

        return True

    def restart(self):
        trace = self.tracing.begin("runtime.restart")

        self.logger.info("Runtime restart requested")
        self.stop()
        self.start()

        self.tracing.finish(trace["trace_id"])

        return True

    def status(self):
        return {
            "state": self._state.value,
            "started": self.started,
        }
