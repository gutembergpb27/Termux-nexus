from datetime import datetime

from nexus.cluster.manager import ClusterManager
from nexus.cluster.replicator import ClusterReplicator


def test_replicator_records_last_successful_sync():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()
    replicator = ClusterReplicator()

    assert replicator.last_sync_at() is None
    assert replicator.sync(leader, follower) is True

    last_sync = replicator.last_sync_at()

    assert isinstance(last_sync, datetime)
    assert last_sync.tzinfo is not None
