from nexus.cluster.manager import ClusterManager


def test_sync_snapshot_between_managers():
    leader = ClusterManager()

    leader.add_node("NODE-A")
    leader.add_node("NODE-B")
    leader.elect_leader("NODE-A")

    follower = ClusterManager()

    assert follower.import_state(leader.export_state()) is True

    assert follower.export_state() == leader.export_state()
    assert follower.leader() == "NODE-A"
    assert follower.followers() == ["NODE-B"]
