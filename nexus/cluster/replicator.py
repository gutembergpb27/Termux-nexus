class ClusterReplicator:
    def sync(self, leader, follower):
        if not leader.needs_sync(follower.export_state()["version"]):
            return False

        return follower.import_state(leader.export_state())
