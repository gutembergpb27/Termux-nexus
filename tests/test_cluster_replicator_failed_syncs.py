from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


class FailingFollower(ClusterManager):
    def import_state(self, snapshot):
        return False


def test_replicator_tracks_failed_syncs():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = FailingFollower()
    replicator = ClusterReplicator()

    assert replicator.sync(leader, follower) is False

    stats = replicator.stats()

    assert stats["sync_count"] == 0
    assert stats["skipped_syncs"] == 0
    assert stats["failed_syncs"] == 1
    assert stats["last_sync_at"] is None
