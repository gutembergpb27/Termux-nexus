from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_counts_successful_syncs():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()

    replicator = ClusterReplicator()

    assert replicator.sync(leader, follower) is True
    assert replicator.sync_count() == 1
