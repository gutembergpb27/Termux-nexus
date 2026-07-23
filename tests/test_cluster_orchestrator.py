from nexus.cluster.manager import ClusterManager
from nexus.cluster.orchestrator import ClusterOrchestrator
from nexus.cluster.replicator import ClusterReplicator


def test_orchestrator_syncs_multiple_followers():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower_a = ClusterManager()
    follower_b = ClusterManager()

    replicator = ClusterReplicator()
    orchestrator = ClusterOrchestrator(replicator)

    result = orchestrator.sync_followers(
        leader,
        [follower_a, follower_b],
    )

    assert result == {
        "synced": 2,
        "skipped": 0,
        "failed": 0,
    }

    assert follower_a.export_state() == leader.export_state()
    assert follower_b.export_state() == leader.export_state()
