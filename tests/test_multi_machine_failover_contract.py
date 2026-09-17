from pathlib import Path


CORE = Path("nexus_distributed_core.py")
HUB = Path("nexus_rendezvous.py")


def read(path):
    return path.read_text(encoding="utf-8-sig")


def test_axis7_requires_externally_reachable_tcp_bind():
    """
    Axis 7 requires nodes running on distinct hosts.

    The runtime TCP server must listen on a non-loopback
    interface so another machine can contact the node.
    """
    source = read(CORE)

    assert (
        'bind(("0.0.0.0", self.tcp_port))' in source
        or "bind(('0.0.0.0', self.tcp_port))" in source
    )


def test_axis7_requires_externally_reachable_hub():
    """
    The rendezvous Hub must be reachable by remote hosts.
    """
    source = read(HUB)

    assert (
        '("0.0.0.0", 8500)' in source
        or "('0.0.0.0', 8500)" in source
    )


def test_axis7_peer_sync_uses_discovered_remote_address():
    """
    Cross-machine state synchronization must use the peer
    address supplied by discovery, not a local loopback
    assumption.
    """
    source = read(CORE)

    start = source.index("    def sync_from_peer")
    fragment = source[start:start + 2200]

    assert 'peer.get("ip"' in fragment
    assert 'peer.get("tcp_port"' in fragment


def test_axis7_requires_configurable_hub_endpoint():
    """
    Each remote node must be able to point to a Hub running
    on another host.
    """
    source = read(CORE)

    assert "NEXUS_HUB_URL" in source


def test_axis7_requires_independent_persistence_path():
    """
    Each physical host must be able to use its own persistent
    state path.
    """
    source = read(CORE)

    assert "NEXUS_DB_PATH" in source


def test_axis7_preserves_single_leader_contract():
    """
    Axis 7 inherits Axis 6.

    Multi-machine failover is invalid if concurrent follower
    promotion can create two leaders.
    """
    source = read(CORE)

    assert "promotion_candidate" in source
    assert "eligible_candidate" in source
    assert 'self.role = "MASTER"' in source


def test_axis7_requires_remote_master_liveness_not_hub_presence():
    """
    Axis 7 inherits Axis 5.

    Hub advertisement alone must not refresh MASTER liveness.
    Successful peer contact/synchronization is required.
    """
    source = read(CORE)

    sync = source.index(
        "self.sync_from_peer(raw_peers[master_node])"
    )

    refresh = source.index(
        "self.last_master_heartbeat = current_time",
        sync,
    )

    assert refresh > sync


def test_axis7_contract_is_not_local_process_certification():
    """
    This file defines readiness prerequisites only.

    Passing these tests MUST NOT be interpreted as proof of
    multi-machine behavior. Final Axis 7 certification requires
    execution on independent hosts.
    """
    required_final_evidence = {
        "distinct_hosts": 3,
        "single_master": True,
        "post_failover_progress": True,
        "old_node_rejoin": True,
        "equal_height": True,
        "equal_tip_hash": True,
        "stability_window": True,
    }

    assert required_final_evidence["distinct_hosts"] == 3
    assert required_final_evidence["single_master"] is True
    assert required_final_evidence["post_failover_progress"] is True
    assert required_final_evidence["old_node_rejoin"] is True
    assert required_final_evidence["equal_height"] is True
    assert required_final_evidence["equal_tip_hash"] is True
    assert required_final_evidence["stability_window"] is True
