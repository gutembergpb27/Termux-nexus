class ClusterReplicator:
    def __init__(self):
        self._sync_count = 0

    def sync(self, leader, follower):
        if not leader.needs_sync(follower.export_state()["version"]):
            return False

        synchronized = follower.import_state(leader.export_state())

        if synchronized:
            self._sync_count += 1

        return synchronized

    def sync_count(self):
        return self._sync_count