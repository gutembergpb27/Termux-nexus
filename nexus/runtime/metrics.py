"""Runtime metrics aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Runtime


class RuntimeMetrics:
    """Aggregate runtime metrics."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def summary(self) -> dict[str, object]:
        """Return aggregated runtime metrics."""

        cluster = self._runtime.cluster

        return {
            "runtime": {
                "started": self._runtime.started,
                "state": self._runtime.state.value,
            },
            "cluster": {
                "nodes": cluster.count(),
                "leader": cluster.leader(),
                "online": len(cluster.online_nodes()),
                "offline": len(cluster.offline_nodes()),
            },
        }