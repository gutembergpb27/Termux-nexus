from datetime import datetime, timezone


class ClusterManager:
    def __init__(self):
        self._nodes = {}
        self._version = 0

    def add_node(self, node_id: str):
        if node_id in self._nodes:
            return False

        self._nodes[node_id] = {
            "role": "FOLLOWER",
            "status": "ONLINE",
            "last_seen": datetime.now(timezone.utc),
        }

        self._version += 1
        return True

    def remove_node(self, node_id: str):
        if node_id not in self._nodes:
            return False

        del self._nodes[node_id]
        self._version += 1
        return True

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

        current_leader = self.leader()

        if current_leader == node_id:
            return True

        for current in self._nodes.values():
            current["role"] = "FOLLOWER"

        node["role"] = "MASTER"
        self._version += 1
        return True

    def leader(self):
        for node_id, node in self._nodes.items():
            if node["role"] == "MASTER":
                return node_id

        return None

    def followers(self):
        return sorted(
            node_id
            for node_id, node in self._nodes.items()
            if node["role"] == "FOLLOWER"
        )

    def online_nodes(self):
        return sorted(
            node_id
            for node_id, node in self._nodes.items()
            if node["status"] == "ONLINE"
        )

    def offline_nodes(self):
        return sorted(
            node_id
            for node_id, node in self._nodes.items()
            if node["status"] == "OFFLINE"
        )

    def export_state(self):
        return {
            "version": self._version,
            "nodes": {
                node_id: {
                    "role": node["role"],
                    "status": node["status"],
                    "last_seen": node["last_seen"],
                }
                for node_id, node in self._nodes.items()
            },
        }

    def import_state(self, snapshot):
        snapshot_version = snapshot.get("version", 0)

        if snapshot_version < self._version:
            return False

        self._nodes = {
            node_id: {
                "role": node["role"],
                "status": node["status"],
                "last_seen": node["last_seen"],
            }
            for node_id, node in snapshot["nodes"].items()
        }

        self._version = snapshot_version
        return True