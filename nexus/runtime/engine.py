"""Runtime engine."""

from __future__ import annotations

from nexus.runtime.cluster import RuntimeCluster
from nexus.runtime.events import RuntimeEvents
from nexus.runtime.health import RuntimeHealth
from nexus.runtime.metrics import RuntimeMetrics
from nexus.runtime.state import RuntimeState


class Runtime:
    """Main Runtime API."""

    def __init__(self):
        self._state = RuntimeState.STOPPED

        self.health = RuntimeHealth(self)
        self.cluster = RuntimeCluster()
        self.metrics = RuntimeMetrics(self)
        self.events = RuntimeEvents()

    @property
    def started(self) -> bool:
        return self._state == RuntimeState.RUNNING

    @property
    def state(self) -> RuntimeState:
        return self._state

    def start(self):
        if self._state == RuntimeState.RUNNING:
            return False

        self._state = RuntimeState.STARTING
        self._state = RuntimeState.RUNNING

        self.events.publish("runtime.started")

        return True

    def stop(self):
        if self._state == RuntimeState.STOPPED:
            return False

        self._state = RuntimeState.STOPPING

        self.events.publish("runtime.stopping")

        self._state = RuntimeState.STOPPED

        self.events.publish("runtime.stopped")

        return True

    def restart(self):
        self.stop()
        self.start()
        return True

    def status(self):
        return {
            "state": self._state.value,
            "started": self.started,
        }
