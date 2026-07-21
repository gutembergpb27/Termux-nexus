from nexus.cluster.manager import ClusterManager


def test_export_state_returns_cluster_snapshot():
    manager = ClusterManager()

    manager.add_node("NODE-A")
    manager.add_node("NODE-B")

    manager.elect_leader("NODE-A")

    manager.touch("NODE-A")
    manager.touch("NODE-B")

    state = manager.export_state()

    assert "nodes" in state

    assert state["nodes"]["NODE-A"]["role"] == "MASTER"
    assert state["nodes"]["NODE-B"]["role"] == "FOLLOWER"

    assert state["nodes"]["NODE-A"]["status"] == "ONLINE"
    assert state["nodes"]["NODE-B"]["status"] == "ONLINE"

    assert "last_seen" in state["nodes"]["NODE-A"]
    assert "last_seen" in state["nodes"]["NODE-B"]