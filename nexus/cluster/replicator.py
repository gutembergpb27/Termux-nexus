from datetime import datetime, timezone


class ClusterReplicator:
    def __init__(self):
        self._sync_count = 0
        self._last_sync_at = None

    def sync(self, leader, follower):
        if not leader.needs_sync(follower.export_state()["version"]):
            return False

        synchronized = follower.import_state(leader.export_state())

        if synchronized:
            self._sync_count += 1
            self._last_sync_at = datetime.now(timezone.utc)

        return synchronized

    def sync_count(self):
        return self._sync_count

    def last_sync_at(self):
        return self._last_sync_at