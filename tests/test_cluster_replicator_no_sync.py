from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_reports_when_sync_not_needed():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()
    follower.import_state(leader.export_state())

    replicator = ClusterReplicator()

    result = replicator.sync(leader, follower)

    assert result is False
