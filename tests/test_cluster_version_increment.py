from nexus.cluster.manager import ClusterManager


def test_cluster_version_increases_when_state_changes():
    manager = ClusterManager()

    initial = manager.export_state()
    assert initial["version"] == 0

    manager.add_node("NODE-A")

    updated = manager.export_state()
    assert updated["version"] == 1
