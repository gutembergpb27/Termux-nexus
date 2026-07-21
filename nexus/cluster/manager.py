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