from datetime import datetime, timezone


class ClusterManager:
    def __init__(self):
        self._nodes = {}

    def add_node(self, node_id: str):
        self._nodes.setdefault(
            node_id,
            {
                "role": "FOLLOWER",
                "status": "ONLINE",
                "last_seen": datetime.now(timezone.utc),
            },
        )

    def remove_node(self, node_id: str):
        self._nodes.pop(node_id, None)

    def nodes(self):
        return sorted(self._nodes)

    def count(self):
        return len(self._nodes)

    def info(self, node_id: str):
        return self._nodes.get(node_id)

    def touch(self, node_id: str):
        node = self._nodes.get(node_id)

        if node is None:
            return False

        node["last_seen"] = datetime.now(timezone.utc)
        node["status"] = "ONLINE"
        return True

    def check_timeouts(self, timeout_seconds: int, now=None):
        if now is None:
            now = datetime.now(timezone.utc)

        offline_nodes = []

        for node_id, node in self._nodes.items():
            elapsed = (now - node["last_seen"]).total_seconds()

            if elapsed > timeout_seconds:
                node["status"] = "OFFLINE"
                offline_nodes.append(node_id)

        return sorted(offline_nodes)
    def elect_leader(self, node_id: str):
        node = self._nodes.get(node_id)

        if node is None:
            return False

        for current in self._nodes.values():
            current["role"] = "FOLLOWER"

        node["role"] = "MASTER"
        return True