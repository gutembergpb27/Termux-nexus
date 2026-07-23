from nexus.cluster.manager import ClusterManager


def test_import_rejects_older_snapshot():
    manager = ClusterManager()

    manager.add_node("NODE-A")
    manager.elect_leader("NODE-A")

    current = manager.export_state()

    older = {
        "version": -1,
        "nodes": current["nodes"],
    }

    assert manager.import_state(older) is False
