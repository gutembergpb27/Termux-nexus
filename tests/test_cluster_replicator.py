from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_syncs_follower_when_needed():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()

    replicator = ClusterReplicator()

    assert replicator.sync(leader, follower) is True
    assert follower.export_state() == leader.export_state()
