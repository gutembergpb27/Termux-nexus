class ClusterOrchestrator:
    def __init__(self, replicator):
        self._replicator = replicator

    def sync_followers(self, leader, followers):
        result = {
            "synced": 0,
            "skipped": 0,
            "failed": 0,
        }

        for follower in followers:
            before = self._replicator.stats()

            synchronized = self._replicator.sync(leader, follower)

            after = self._replicator.stats()

            if synchronized:
                result["synced"] += 1
            elif after["skipped_syncs"] > before["skipped_syncs"]:
                result["skipped"] += 1
            elif after["failed_syncs"] > before["failed_syncs"]:
                result["failed"] += 1

        return result
