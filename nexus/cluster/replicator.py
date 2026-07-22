from datetime import datetime, timezone


class ClusterReplicator:
    def __init__(self):
        self._sync_count = 0
        self._skipped_syncs = 0
        self._last_sync_at = None

    def sync(self, leader, follower):
        if not leader.needs_sync(follower.export_state()["version"]):
            self._skipped_syncs += 1
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

    def stats(self):
        return {
            "sync_count": self._sync_count,
            "skipped_syncs": self._skipped_syncs,
            "last_sync_at": self._last_sync_at,
        }