"""Runtime cluster facade."""

from __future__ import annotations

from copy import deepcopy

from nexus.cluster import ClusterManager


class RuntimeCluster:
    """High-level facade for cluster operations."""

    def __init__(self):
        self._manager = ClusterManager()

    def add_node(self, node_id: str):
        return self._manager.add_node(node_id)

    def remove_node(self, node_id: str):
        return self._manager.remove_node(node_id)

    def nodes(self):
        return self._manager.nodes()

    def count(self):
        return self._manager.count()

    def leader(self):
        return self._manager.leader()

    def followers(self):
        return self._manager.followers()

    def online_nodes(self):
        return self._manager.online_nodes()

    def offline_nodes(self):
        return self._manager.offline_nodes()

    def elect_leader(self, node_id: str):
        return self._manager.elect_leader(node_id)

    def touch(self, node_id: str):
        return self._manager.touch(node_id)

    def check_timeouts(self, timeout_seconds: int):
        return self._manager.check_timeouts(timeout_seconds)

    def snapshot(self):
        return deepcopy(self._manager.export_state())