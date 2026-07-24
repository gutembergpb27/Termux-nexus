from nexus.runtime.cluster import RuntimeCluster


def test_runtime_cluster_starts_empty():
    cluster = RuntimeCluster()

    assert cluster.nodes() == []
    assert cluster.count() == 0
    assert cluster.leader() is None
    assert cluster.followers() == []
    assert cluster.online_nodes() == []
    assert cluster.offline_nodes() == []


def test_runtime_cluster_manages_nodes():
    cluster = RuntimeCluster()

    assert cluster.add_node("NODE-A") is True
    assert cluster.add_node("NODE-A") is False
    assert cluster.add_node("NODE-B") is True

    assert cluster.nodes() == ["NODE-A", "NODE-B"]
    assert cluster.count() == 2

    assert cluster.remove_node("NODE-B") is True
    assert cluster.remove_node("NODE-B") is False

    assert cluster.nodes() == ["NODE-A"]
    assert cluster.count() == 1


def test_runtime_cluster_elects_leader():
    cluster = RuntimeCluster()

    cluster.add_node("NODE-A")
    cluster.add_node("NODE-B")

    assert cluster.elect_leader("NODE-A") is True
    assert cluster.leader() == "NODE-A"
    assert cluster.followers() == ["NODE-B"]

    assert cluster.elect_leader("UNKNOWN") is False
    assert cluster.leader() == "NODE-A"


def test_runtime_cluster_tracks_node_status():
    cluster = RuntimeCluster()

    cluster.add_node("NODE-A")

    assert cluster.online_nodes() == ["NODE-A"]
    assert cluster.offline_nodes() == []

    assert cluster.check_timeouts(-1) == ["NODE-A"]
    assert cluster.online_nodes() == []
    assert cluster.offline_nodes() == ["NODE-A"]

    assert cluster.touch("NODE-A") is True
    assert cluster.online_nodes() == ["NODE-A"]
    assert cluster.offline_nodes() == []

    assert cluster.touch("UNKNOWN") is False


def test_runtime_cluster_snapshot_is_independent():
    cluster = RuntimeCluster()

    cluster.add_node("NODE-A")
    snapshot = cluster.snapshot()

    snapshot["nodes"]["NODE-A"]["role"] = "BROKEN"

    assert cluster.snapshot()["nodes"]["NODE-A"]["role"] == "FOLLOWER"