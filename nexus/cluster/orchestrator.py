class ClusterOrchestrator:
    def __init__(self, replicator):
        self._replicator = replicator
        self._cycle = 0

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

    def sync_cluster(self, nodes, leader_id):
        leader = nodes[leader_id]

        followers = [
            node
            for node_id, node in nodes.items()
            if node_id != leader_id
        ]

        return self.sync_followers(leader, followers)

    def sync_online_cluster(self, leader, nodes, leader_id):
        followers = []
        offline = 0

        for node_id in leader.followers():
            if node_id not in nodes:
                continue

            info = leader.info(node_id)

            if info["status"] != "ONLINE":
                offline += 1
                continue

            followers.append(nodes[node_id])

        result = self.sync_followers(leader, followers)
        result["offline"] = offline
        return result

    def run_cycle(self, leader, nodes, leader_id):
        self._cycle += 1

        report = self.sync_online_cluster(
            leader,
            nodes,
            leader_id,
        )

        report["cycle"] = self._cycle
        return report
