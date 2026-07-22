from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_tracks_skipped_syncs():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()
    replicator = ClusterReplicator()

    assert replicator.sync(leader, follower) is True
    assert replicator.sync(leader, follower) is False

    stats = replicator.stats()

    assert stats["sync_count"] == 1
    assert stats["skipped_syncs"] == 1
