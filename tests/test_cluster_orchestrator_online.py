from datetime import datetime, timedelta, timezone

from nexus.cluster.manager import ClusterManager
from nexus.cluster.orchestrator import ClusterOrchestrator
from nexus.cluster.replicator import ClusterReplicator


def test_orchestrator_ignores_offline_followers():
    leader = ClusterManager()
    leader.add_node("NODE-A")
    leader.add_node("NODE-B")
    leader.add_node("NODE-C")
    leader.elect_leader("NODE-A")

    leader.info("NODE-C")["last_seen"] = (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    )
    leader.check_timeouts(timeout_seconds=30)

    follower_b = ClusterManager()
    follower_c = ClusterManager()

    orchestrator = ClusterOrchestrator(ClusterReplicator())

    result = orchestrator.sync_online_cluster(
        leader,
        {
            "NODE-A": leader,
            "NODE-B": follower_b,
            "NODE-C": follower_c,
        },
        leader_id="NODE-A",
    )

    assert result == {
        "synced": 1,
        "skipped": 0,
        "failed": 0,
        "offline": 1,
    }

    assert follower_b.export_state() == leader.export_state()
    assert follower_c.export_state() != leader.export_state()
