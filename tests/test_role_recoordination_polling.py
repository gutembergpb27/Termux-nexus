import inspect

from nexus_distributed_core import NexusDistributedCore


def polling_source():
    return inspect.getsource(
        NexusDistributedCore.async_polling_loop
    )


def position(source, text):
    value = source.find(text)
    assert value >= 0, f"missing polling anchor: {text!r}"
    return value


def test_polling_calls_role_reconciliation_after_peer_snapshot():
    source = polling_source()

    peers = position(
        source,
        "self.peers = raw_peers",
    )
    reconcile = position(
        source,
        "self.reconcile_master_role(raw_peers)",
    )

    assert peers < reconcile


def test_polling_reconciles_before_remote_master_selection():
    source = polling_source()

    reconcile = position(
        source,
        "self.reconcile_master_role(raw_peers)",
    )
    master_selection = position(
        source,
        "master_node = next(",
    )

    assert reconcile < master_selection


def test_polling_emits_corrective_heartbeat_after_demotion():
    source = polling_source()

    reconcile = position(
        source,
        "role_changed = self.reconcile_master_role(raw_peers)",
    )
    role_changed_branch = position(
        source,
        "if role_changed:",
    )

    assert reconcile < role_changed_branch

    after_branch = source[role_changed_branch:]

    assert '"/heartbeat"' in after_branch
    assert "self.build_heartbeat_envelope()" in after_branch


def test_polling_syncs_remote_master_only_while_local_follower():
    source = polling_source()

    follower_guard = position(
        source,
        'if master_node and self.role == "FOLLOWER":',
    )
    sync = position(
        source,
        "self.sync_from_peer(raw_peers[master_node])",
    )

    assert follower_guard < sync


def test_polling_promotion_remains_after_reconciliation():
    source = polling_source()

    reconcile = position(
        source,
        "self.reconcile_master_role(raw_peers)",
    )
    promotion = position(
        source,
        'self.role = "MASTER"',
    )

    assert reconcile < promotion


def test_corrective_heartbeat_precedes_master_sync():
    source = polling_source()

    role_changed_branch = position(
        source,
        "if role_changed:",
    )
    sync = position(
        source,
        "self.sync_from_peer(raw_peers[master_node])",
    )

    branch_to_sync = source[
        role_changed_branch:sync
    ]

    assert '"/heartbeat"' in branch_to_sync
    assert "self.build_heartbeat_envelope()" in branch_to_sync


def test_polling_does_not_mutate_node_identity():
    source = polling_source()

    assert "self.node_id =" not in source


def test_master_heartbeat_refresh_requires_successful_peer_sync():
    """
    Hub advertisement is discovery, not proof of MASTER liveness.

    The follower may refresh last_master_heartbeat only after
    successful peer synchronization/contact.
    """
    source = polling_source()

    follower_branch = position(
        source,
        'if master_node and self.role == "FOLLOWER":',
    )

    sync_call = source.index(
        "self.sync_from_peer(raw_peers[master_node])",
        follower_branch,
    )

    heartbeat_refresh = source.index(
        "self.last_master_heartbeat = current_time",
        follower_branch,
    )

    except_branch = source.index(
        "except Exception as exc:",
        sync_call,
    )

    assert sync_call < heartbeat_refresh < except_branch, (
        "MASTER liveness must not be refreshed merely because "
        "the Hub still advertises a MASTER. Successful peer "
        "contact must occur before heartbeat refresh."
    )


def test_unreachable_advertised_master_cannot_suppress_failover_timeout():
    """
    A stale Hub MASTER advertisement must not suppress failover.

    Failed synchronization leaves the follower eligible for the
    normal MASTER-missing timeout path.
    """
    source = polling_source()

    follower_branch = position(
        source,
        'if master_node and self.role == "FOLLOWER":',
    )

    sync_call = source.index(
        "self.sync_from_peer(raw_peers[master_node])",
        follower_branch,
    )

    heartbeat_refresh = source.index(
        "self.last_master_heartbeat = current_time",
        sync_call,
    )

    reachable_true = source.index(
        "master_reachable = True",
        heartbeat_refresh,
    )

    sync_except = source.index(
        "except Exception as exc:",
        reachable_true,
    )

    failover_guard = source.index(
        'if self.role == "FOLLOWER" and not master_reachable:',
        sync_except,
    )

    timeout = source.index(
        "delta = current_time - self.last_master_heartbeat",
        failover_guard,
    )

    promotion = source.index(
        'self.role = "MASTER"',
        timeout,
    )

    assert (
        sync_call
        < heartbeat_refresh
        < reachable_true
        < sync_except
        < failover_guard
        < timeout
        < promotion
    )
