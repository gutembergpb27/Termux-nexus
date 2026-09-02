from nexus_distributed_core import NexusDistributedCore


def make_core(node_id, role):
    core = object.__new__(NexusDistributedCore)
    core.node_id = node_id
    core.role = role
    return core


def test_master_yields_to_competing_master_with_higher_node_id():
    core = make_core("NODE-A", "MASTER")

    changed = core.reconcile_master_role(
        {
            "NODE-B": {
                "node_id": "NODE-B",
                "role": "MASTER",
            }
        }
    )

    assert changed is True
    assert core.node_id == "NODE-A"
    assert core.role == "FOLLOWER"


def test_master_keeps_role_against_competing_master_with_lower_node_id():
    core = make_core("NODE-B", "MASTER")

    changed = core.reconcile_master_role(
        {
            "NODE-A": {
                "node_id": "NODE-A",
                "role": "MASTER",
            }
        }
    )

    assert changed is False
    assert core.node_id == "NODE-B"
    assert core.role == "MASTER"


def test_follower_remains_follower_when_master_exists():
    core = make_core("NODE-A", "FOLLOWER")

    changed = core.reconcile_master_role(
        {
            "NODE-B": {
                "node_id": "NODE-B",
                "role": "MASTER",
            }
        }
    )

    assert changed is False
    assert core.node_id == "NODE-A"
    assert core.role == "FOLLOWER"


def test_role_recoordination_ignores_local_peer_record():
    core = make_core("NODE-A", "MASTER")

    changed = core.reconcile_master_role(
        {
            "NODE-A": {
                "node_id": "NODE-A",
                "role": "MASTER",
            }
        }
    )

    assert changed is False
    assert core.node_id == "NODE-A"
    assert core.role == "MASTER"


def test_role_recoordination_preserves_node_identity():
    core = make_core("NODE-A", "MASTER")
    original_node_id = core.node_id

    core.reconcile_master_role(
        {
            "NODE-Z": {
                "node_id": "NODE-Z",
                "role": "MASTER",
            }
        }
    )

    assert core.node_id == original_node_id
