from nexus.cluster.manager import ClusterManager
from nexus.cluster.orchestrator import ClusterOrchestrator
from nexus.cluster.replicator import ClusterReplicator


def test_orchestrator_runs_sync_cycle():
    leader = ClusterManager()

    leader.add_node("NODE-A")
    leader.add_node("NODE-B")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()

    orchestrator = ClusterOrchestrator(ClusterReplicator())

    report = orchestrator.run_cycle(
        leader,
        {
            "NODE-A": leader,
            "NODE-B": follower,
        },
        leader_id="NODE-A",
    )

    assert report["cycle"] == 1
    assert report["synced"] == 1
    assert report["failed"] == 0
    assert report["skipped"] == 0
    assert report["offline"] == 0
