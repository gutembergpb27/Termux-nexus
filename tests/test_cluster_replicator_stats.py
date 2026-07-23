from datetime import datetime

from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_stats():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()
    replicator = ClusterReplicator()

    assert replicator.sync(leader, follower) is True

    stats = replicator.stats()

    assert stats["sync_count"] == 1
    assert isinstance(stats["last_sync_at"], datetime)
