from nexus.cluster.manager import ClusterManager


def test_import_state_replaces_cluster_snapshot():
    source = ClusterManager()

    source.add_node("NODE-A")
    source.add_node("NODE-B")
    source.elect_leader("NODE-A")

    snapshot = source.export_state()

    target = ClusterManager()
    target.add_node("NODE-X")

    target.import_state(snapshot)

    assert target.export_state() == snapshot
    assert target.leader() == "NODE-A"
    assert target.followers() == ["NODE-B"]
    assert target.count() == 2