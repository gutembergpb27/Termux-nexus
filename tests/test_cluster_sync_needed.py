from nexus.cluster.manager import ClusterManager


def test_sync_not_needed_when_versions_match():
    leader = ClusterManager()

    leader.add_node("NODE-A")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()
    follower.import_state(leader.export_state())

    assert follower.export_state()["version"] == leader.export_state()["version"]

    assert leader.needs_sync(follower.export_state()["version"]) is False
