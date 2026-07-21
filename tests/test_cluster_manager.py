from nexus.cluster.manager import ClusterManager


def test_manager_starts_empty():
    manager = ClusterManager()

    assert manager.count() == 0
    assert manager.nodes() == []


def test_add_node():
    manager = ClusterManager()

    manager.add_node("NODE-A")

    assert manager.count() == 1
    assert manager.nodes() == ["NODE-A"]


def test_add_multiple_nodes():
    manager = ClusterManager()

    manager.add_node("NODE-A")
    manager.add_node("NODE-B")

    assert manager.count() == 2
    assert set(manager.nodes()) == {"NODE-A", "NODE-B"}


def test_duplicate_node_is_ignored():
    manager = ClusterManager()

    manager.add_node("NODE-A")
    manager.add_node("NODE-A")

    assert manager.count() == 1


def test_remove_node():
    manager = ClusterManager()

    manager.add_node("NODE-A")
    manager.remove_node("NODE-A")

    assert manager.count() == 0
    assert manager.nodes() == []


def test_new_node_is_online():
    manager = ClusterManager()

    manager.add_node("NODE-A")

    assert manager.info("NODE-A")["status"] == "ONLINE"


def test_new_node_is_follower():
    manager = ClusterManager()

    manager.add_node("NODE-A")

    assert manager.info("NODE-A")["role"] == "FOLLOWER"


def test_unknown_node_returns_none():
    manager = ClusterManager()

    assert manager.info("UNKNOWN") is None


def test_new_node_has_last_seen():
    manager = ClusterManager()

    manager.add_node("NODE-A")

    assert manager.info("NODE-A")["last_seen"] is not None


def test_touch_updates_last_seen():
    manager = ClusterManager()

    manager.add_node("NODE-A")

    first = manager.info("NODE-A")["last_seen"]

    manager.touch("NODE-A")

    second = manager.info("NODE-A")["last_seen"]

    assert second >= first