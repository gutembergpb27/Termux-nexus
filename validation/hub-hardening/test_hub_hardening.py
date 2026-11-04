"""W07 regression tests: original hub (characterization) vs experimental hub.

Loopback only (127.0.0.1, ephemeral ports). The original hub is exercised as
its handler class on an in-process HTTPServer; its ``__main__`` (0.0.0.0:8500)
never runs. ``test_original_*`` tests PASS when the documented limitation is
reproduced; if one starts failing, the original behavior changed.

Run: python -B -X dev -m pytest -p no:cacheprovider -W error::ResourceWarning test_hub_hardening.py
"""
from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import experimental_hub as xh  # noqa: E402
import hub_probes as hp  # noqa: E402
import nexus_rendezvous as original  # noqa: E402
from nexus_protocol import NexusProtocol  # noqa: E402

REPO_ROOT = HERE.parents[1]
EXPECTED_BLOBS = {
    "nexus_rendezvous.py": "d61fedd2d417ed85d6759239e16751fac7920298",
    "nexus_distributed_core.py": "eb8a48da88a75f9d58c954f8afeed86c2af27f93",
}


@pytest.fixture
def secret():
    return hp.new_test_secret()


@pytest.fixture(autouse=True)
def no_leaks():
    """Every test must leave no hub threads behind and the original globals intact."""
    before = {t.ident for t in threading.enumerate()}
    saved = (original.PROTOCOL, original.REPLAY_CACHE, original.PEERS)
    yield
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        leaked = [t.name for t in threading.enumerate()
                  if t.ident not in before and t.is_alive()
                  and (t.name.startswith("hub-") or t.name == "original-hub-under-test")]
        if not leaked:
            break
        time.sleep(0.05)
    assert not leaked, f"leaked threads: {leaked}"
    assert (original.PROTOCOL, original.REPLAY_CACHE, original.PEERS) == saved


@pytest.fixture
def target_factory(secret):
    created = []

    def make(kind, **kwargs):
        target = hp.make_target(kind, secret, **kwargs)
        created.append(target)
        return target

    yield make
    for target in created:
        port = target.port
        target.stop()
        with socket.socket() as probe:
            probe.settimeout(0.5)
            assert probe.connect_ex((hp.LOOPBACK, port)) != 0, "port still open after stop"


# ----------------------------------------------------------------------
# Configuration and bind policy (items 25, 26)
# ----------------------------------------------------------------------

def test_default_bind_is_loopback():
    import inspect
    assert inspect.signature(xh.HardenedHub.__init__).parameters["host"].default == "127.0.0.1"
    assert "127.0.0.1" in inspect.getsource(xh.main)  # CLI --host default


@pytest.mark.parametrize("host", ["0.0.0.0", "::", ""])
def test_wildcard_bind_requires_opt_in(secret, host):
    with pytest.raises(ValueError, match="wildcard"):
        xh.HardenedHub(secret, host=host, port=0)


@pytest.mark.parametrize("field,value", [
    ("max_connections", 0), ("max_connections", 5000), ("max_per_client", 0), ("max_per_client", 64),
    ("socket_timeout_s", 0), ("request_deadline_s", 0.1),
    ("max_body_bytes", 65537), ("max_body_bytes", 0),
    ("shutdown_grace_s", 0), ("peer_timeout_s", -1), ("listen_backlog", 0),
])
def test_limits_reject_unsafe_values(field, value):
    with pytest.raises(ValueError):
        xh.HubLimits(**{field: value}).validate()


def test_limits_defaults_preserve_original_contract():
    limits = xh.HubLimits()
    limits.validate()
    assert limits.max_body_bytes == 65536
    assert limits.peer_timeout_s == original.PEER_TIMEOUT
    assert limits.message_ttl_s == original.MESSAGE_TTL


def test_validation_logic_is_shared_not_copied():
    import inspect
    source = inspect.getsource(xh)
    assert "original.register_peer(" in source
    assert "original.update_peer_heartbeat(" in source
    assert "def register_peer" not in source and "def verify_envelope" not in source


def test_runtime_files_untouched():
    for name, blob in EXPECTED_BLOBS.items():
        out = subprocess.run(["git", "-C", str(REPO_ROOT), "hash-object", name],
                             capture_output=True, text=True, check=True)
        assert out.stdout.strip() == blob, name


# ----------------------------------------------------------------------
# Items 11, 12, 14: incomplete requests, idle clients, slow drip
# ----------------------------------------------------------------------

def test_original_characterization_idle_client_freezes_hub(target_factory):
    result = hp.probe_idle_client(target_factory("original"), observe_s=2.5)
    assert result["concurrent_peers_request"]["error"] == "timeout"
    assert result["idle_connection"]["closed"] is False


def test_experimental_idle_client_does_not_block_and_is_closed(target_factory):
    target = target_factory("experimental")
    result = hp.probe_idle_client(target, observe_s=2.5)
    assert result["concurrent_peers_request"]["status"] == 200
    assert result["concurrent_peers_request"]["elapsed_s"] < 0.5
    assert result["idle_connection"]["closed"] is True
    assert target.hub.stats.snapshot().get("socket_timeout", 0) >= 1


def test_original_characterization_partial_headers_freeze_hub(target_factory):
    result = hp.probe_partial_headers(target_factory("original"), observe_s=2.5)
    assert result["concurrent_peers_request"]["error"] == "timeout"
    assert result["partial_connection"]["closed"] is False


def test_experimental_partial_headers_time_out(target_factory):
    result = hp.probe_partial_headers(target_factory("experimental"), observe_s=2.5)
    assert result["concurrent_peers_request"]["status"] == 200
    assert result["partial_connection"]["closed"] is True


def test_original_characterization_partial_body_freezes_hub(target_factory, secret):
    result = hp.probe_partial_body(target_factory("original"), secret, observe_s=2.5)
    assert result["concurrent_peers_request"]["error"] == "timeout"
    assert result["partial_connection"]["closed"] is False


def test_experimental_partial_body_times_out_without_registering(target_factory, secret):
    target = target_factory("experimental")
    result = hp.probe_partial_body(target, secret, observe_s=2.5)
    assert result["concurrent_peers_request"]["status"] == 200
    assert result["partial_connection"]["closed"] is True
    assert result["peer_registered"] is False


def test_original_characterization_slow_drip_never_cut(target_factory):
    result = hp.probe_slow_drip(target_factory("original"), duration_s=3.0)
    assert result["survived_full_window"] is True


def test_experimental_slow_drip_cut_by_request_deadline(target_factory):
    target = target_factory("experimental")
    result = hp.probe_slow_drip(target, duration_s=4.0)
    deadline = hp.TEST_LIMITS.request_deadline_s
    assert result["survived_full_window"] is False
    assert deadline - 0.1 <= result["cut_by_server_after_s"] <= deadline + 1.0
    assert target.hub.stats.snapshot().get("deadline_closed", 0) >= 1


# ----------------------------------------------------------------------
# Item 13: concurrency; item 18: HMAC/replay under concurrency
# ----------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["original", "experimental"])
def test_concurrent_requests_all_served(target_factory, secret, kind):
    result = hp.probe_concurrent(target_factory(kind), secret, clients=20)
    assert result["register_200"] == 20 and result["peers_200"] == 20, result
    assert result["final_peer_count"] == 20


@pytest.mark.parametrize("kind", ["original", "experimental"])
def test_parallel_replay_accepted_exactly_once(target_factory, secret, kind):
    result = hp.probe_parallel_replay(target_factory(kind), secret, copies=16)
    assert result == {"copies": 16, "accepted": 1, "rejected_401": 15, "other": []}


def test_auth_and_contract_matrix_identical(target_factory, secret):
    """Items 18, 19, 29: every signed/invalid case gets the same status and body."""
    a = {row["case"]: row for row in hp.auth_matrix(target_factory("original"), secret)}
    b = {row["case"]: row for row in hp.auth_matrix(target_factory("experimental"), secret)}
    assert a.keys() == b.keys()
    allowed_differences = {"get_unknown_path"}
    for case in a:
        if case in allowed_differences:
            continue
        assert a[case]["status"] == b[case]["status"], case
        if case == "get_peers":
            assert a[case]["body"].keys() == b[case]["body"].keys()
            for node_id in a[case]["body"]:
                assert a[case]["body"][node_id].keys() == b[case]["body"][node_id].keys()
        else:
            assert a[case]["body"] == b[case]["body"], case
    # Expected security outcomes, not just parity.
    expect = {
        "register_valid": 200, "register_replay": 401, "heartbeat_valid": 200,
        "register_tampered": 401, "register_wrong_secret": 401, "register_expired": 401,
        "register_future": 401, "register_sender_mismatch": 400, "register_bad_role": 400,
        "register_missing_field": 401, "heartbeat_unregistered": 400,
        "heartbeat_wrong_secret": 401, "oversized_length": 400, "missing_length": 400,
    }
    for case, status in expect.items():
        assert b[case]["status"] == status, case
    assert a["get_unknown_path"]["status"] == "RemoteDisconnected"  # original: no response
    assert b["get_unknown_path"]["status"] == 404


@pytest.mark.parametrize("kind", ["original", "experimental"])
def test_oversized_headers_rejected(target_factory, kind):
    assert hp.oversized_header(target_factory(kind)) == {"header_line_70k": 431, "headers_150": 431}


def test_unsigned_get_peers_still_public_in_both(target_factory):
    """Documented, not fixed: nodes fetch /peers unsigned, so auth would break them."""
    for kind in ("original", "experimental"):
        assert hp.get_peers(target_factory(kind).port)["status"] == 200


# ----------------------------------------------------------------------
# Item 15: shutdown with pending connections
# ----------------------------------------------------------------------

def test_original_characterization_shutdown_blocks_on_pending_client(target_factory):
    result = hp.probe_shutdown_pending(target_factory("original"), hold_s=1.5)
    assert result["shutdown_completed_with_client_open"] is False
    assert result["completed_after_client_closed"] is True


def test_experimental_shutdown_with_pending_clients_is_bounded(target_factory):
    target = target_factory("experimental")
    for _ in range(3):
        target.raw_connect()
    time.sleep(0.2)
    report = target.hub.close()
    assert report["clean"] is True and report["threads_alive"] == []
    assert report["duration_s"] <= hp.TEST_LIMITS.shutdown_grace_s + 0.5


def test_experimental_rejects_new_connections_after_close(target_factory, secret):
    target = target_factory("experimental")
    port = target.port
    target.hub.close()
    with socket.socket() as probe:
        probe.settimeout(0.5)
        assert probe.connect_ex((hp.LOOPBACK, port)) != 0


def test_experimental_close_is_idempotent(target_factory):
    target = target_factory("experimental")
    first = target.hub.close()
    assert target.hub.close() is first


# ----------------------------------------------------------------------
# Item 16: resource limits
# ----------------------------------------------------------------------

def test_experimental_capacity_limit_rejects_fast_and_recovers(target_factory):
    target = target_factory("experimental", limits=hp.CAPACITY_LIMITS)
    result = hp.probe_capacity(target, extra=4)
    assert result["held"] == hp.CAPACITY_LIMITS.max_connections
    assert result["overflow_503"] == 4 and result["overflow_closed_fast"] == 4
    assert result["peers_during_saturation"] == 503
    assert result["peers_after_release"] == 200
    stats = target.hub.stats.snapshot()
    # All loopback clients share 127.0.0.1, so the per-client cap (== slot cap here) answers first.
    assert stats.get("rejected_capacity", 0) + stats.get("rejected_client_limit", 0) >= 5
    assert target.hub.active_connections() == 0


def test_experimental_per_client_cap_and_global_cap_are_distinct(target_factory):
    limits = xh.HubLimits(max_connections=6, max_per_client=4, socket_timeout_s=3.0,
                          request_deadline_s=4.0, shutdown_grace_s=1.0)
    target = target_factory("experimental", limits=limits)
    try:
        second = [target.raw_connect(source="127.0.0.2") for _ in range(2)]
    except OSError:
        pytest.skip("127.0.0.2 not usable as a loopback source on this host")
    first = [target.raw_connect() for _ in range(4)]
    time.sleep(0.3)
    over_client = hp.read_response_then_close(target.raw_connect(), 1.0)
    over_global = hp.read_response_then_close(target.raw_connect(source="127.0.0.2"), 1.0)
    assert "too many connections from client" in over_client["data"]
    assert "hub at capacity" in over_global["data"]
    stats = target.hub.stats.snapshot()
    assert stats["rejected_client_limit"] == 1 and stats["rejected_capacity"] == 1
    for sock in first + second:
        sock.close()
    time.sleep(0.3)
    assert hp.get_peers(target.port)["status"] == 200
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and (target.hub._per_client or target.hub.active_connections()):
        time.sleep(0.02)  # the worker releases its counters just after replying
    assert dict(target.hub._per_client) == {} and target.hub.active_connections() == 0


def test_original_characterization_capacity_blocks(target_factory):
    result = hp.probe_capacity(target_factory("original"), extra=2, max_connections=4)
    assert result["peers_during_saturation"] == "timeout"
    assert result["overflow_503"] == 0


def test_experimental_thread_count_bounded_under_flood(target_factory):
    target = target_factory("experimental")
    socks = []
    for _ in range(40):
        try:
            socks.append(target.raw_connect(timeout=1.0))
        except OSError:
            pass
    time.sleep(0.3)
    workers = [t for t in threading.enumerate() if t.name == "hub-conn"]
    assert len(workers) <= hp.TEST_LIMITS.max_connections
    target.close_clients()


def test_body_limit_cannot_exceed_original(secret):
    with pytest.raises(ValueError):
        xh.HardenedHub(secret, port=0, limits=xh.HubLimits(max_body_bytes=1 << 20))


def test_allowlist_rejects_unlisted_client(target_factory):
    blocked = target_factory("experimental", allowed_networks=["10.0.0.0/8"])
    r = hp.get_peers(blocked.port)
    assert r["status"] == 403 and blocked.hub.stats.snapshot()["rejected_client"] == 1
    allowed = target_factory("experimental", allowed_networks=["127.0.0.0/8"])
    assert hp.get_peers(allowed.port)["status"] == 200


def test_original_characterization_port_can_be_shared_on_windows(target_factory):
    result = hp.probe_port_sharing(target_factory("original"))
    if os.name == "nt":
        assert result["second_bind_allowed"] is True
    else:
        assert result["second_bind_allowed"] is False


def test_experimental_port_is_exclusive(target_factory):
    assert hp.probe_port_sharing(target_factory("experimental"))["second_bind_allowed"] is False


# ----------------------------------------------------------------------
# Item 17: exception handling; reaper robustness
# ----------------------------------------------------------------------

def test_original_characterization_handler_exception_drops_connection(target_factory, capsys):
    result = hp.probe_unhandled_exception(target_factory("original"))
    assert result["while_corrupt"] == "RemoteDisconnected"
    assert result["after_repair"] == 200


def test_experimental_handler_exception_returns_500_and_keeps_serving(target_factory):
    target = target_factory("experimental")
    result = hp.probe_unhandled_exception(target)
    assert result["while_corrupt"] == 500
    assert result["while_corrupt_body"] == {"error": "internal error"}
    assert result["after_repair"] == 200
    assert target.hub.stats.snapshot()["handler_error"] == 1


def test_experimental_reaper_expires_peers_and_survives_errors(target_factory, secret):
    target = target_factory("experimental")
    protocol = NexusProtocol(secret)
    assert hp.post_json(target.port, "/register", hp.registration(protocol, "NODE-OLD"))["status"] == 200
    with target.hub.state_lock:
        target.hub.peers["NODE-OLD"]["last_seen"] -= 10_000
        target.hub.peers["BROKEN"] = ["not-a-dict"]
    time.sleep(0.6)
    stats = target.hub.stats.snapshot()
    assert stats.get("reaper_error", 0) >= 1
    reaper = [t for t in threading.enumerate() if t.name == "hub-reaper"]
    assert reaper and reaper[0].is_alive()
    with target.hub.state_lock:
        target.hub.peers.pop("BROKEN")
    time.sleep(0.6)
    assert "NODE-OLD" not in target.hub.peers
    assert target.hub.stats.snapshot().get("peers_reaped", 0) >= 1


def test_peers_view_excludes_expired_even_before_reap(target_factory, secret):
    target = target_factory("experimental", limits=xh.HubLimits(reap_interval_s=60, shutdown_grace_s=1.0))
    hp.post_json(target.port, "/register", hp.registration(NexusProtocol(secret), "NODE-X"))
    with target.hub.state_lock:
        target.hub.peers["NODE-X"]["last_seen"] -= original.PEER_TIMEOUT + 1
    assert hp.get_peers(target.port)["json"] == {}


# ----------------------------------------------------------------------
# Items 19, 20: runtime client compatibility and unavailability
# ----------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["original", "experimental"])
def test_runtime_node_client_compatible(target_factory, secret, kind):
    result = hp.probe_node_client(target_factory(kind), secret)
    assert all(result[k] for k in ("a_register", "c_register", "a_heartbeat", "c_heartbeat", "peers_ok"))
    assert result["peer_ids"] == ["NODE-A", "NODE-C"]
    assert result["record_keys"] == ["capabilities", "ip", "last_seen", "load", "node_id",
                                     "protocol_version", "role", "tcp_port", "web_port"]
    assert result["a_role"] == "MASTER" and result["a_ip"] == "127.0.0.1"
    assert result["a_ports"] == [8081, 9091] and result["has_load_after_heartbeat"]


def test_original_characterization_node_client_stalls_while_hub_blocked(target_factory, secret):
    result = hp.probe_node_client_unavailable(target_factory("original"), secret, "blocked")
    assert result["register_ok"] is False
    assert result["elapsed_s"] >= 1.9  # the node's urllib timeout (2 s) is the only bound
    assert result["peers"]["ok"] is False


def test_experimental_node_client_served_despite_idle_client(target_factory, secret):
    result = hp.probe_node_client_unavailable(target_factory("experimental"), secret, "blocked")
    assert result["register_ok"] is True and result["elapsed_s"] < 0.5
    assert result["peers"]["ok"] is True


def test_node_client_fails_fast_when_hub_down(secret):
    target = hp.make_target("experimental", secret)
    port = target.port
    target.stop()
    node = hp.make_node_client(port, secret, "NODE-B", "FOLLOWER", 8082, 9092)
    started = time.monotonic()
    assert node.post_envelope("/register", node.build_registration_envelope()) is False
    assert time.monotonic() - started < 2.5
    assert hp.node_fetch_peers(node)["ok"] is False


def test_protocol_not_configured_returns_503(target_factory):
    target = hp.ExperimentalHubTarget(None, limits=hp.TEST_LIMITS)
    try:
        r = hp.post_json(target.port, "/register", {"x": 1})
        assert r["status"] == 503 and r["json"] == {"error": "protocol not configured"}
    finally:
        target.stop()


# ----------------------------------------------------------------------
# Item 23, 36: CLI process — graceful stop, no secret in output
# ----------------------------------------------------------------------

def _cli(args, secret, **kw):
    env = {k: v for k, v in os.environ.items() if k != "NEXUS_SECRET_KEY"}
    if secret is not None:
        env["NEXUS_SECRET_KEY"] = secret
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen([sys.executable, "-B", str(HERE / "experimental_hub.py"), *args],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=env, creationflags=flags, cwd=str(HERE), **kw)


def test_cli_graceful_stop_and_no_secret_in_output(secret):
    proc = _cli(["--port", "0"], secret)
    try:
        line = proc.stdout.readline()
        match = re.search(r"hub_listening host=127\.0\.0\.1 port=(\d+)", line)
        if not match:  # logging line may come first
            line = proc.stdout.readline()
            match = re.search(r"hub_listening host=127\.0\.0\.1 port=(\d+)", line)
        assert match, line
        port = int(match.group(1))
        assert hp.get_peers(port)["status"] == 200
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=10)
        assert proc.returncode == 0, out
        assert "hub_closed clean=True" in out
        assert secret not in line + out
        with socket.socket() as probe:
            probe.settimeout(0.5)
            assert probe.connect_ex((hp.LOOPBACK, port)) != 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)


@pytest.mark.parametrize("args,secret_value,expected", [
    (["--port", "0"], None, "hub_error=missing_secret"),
    (["--port", "0", "--host", "0.0.0.0"], "w07-test-cli-secret-0000", "hub_error=config"),
    (["--port", "0", "--max-connections", "0"], "w07-test-cli-secret-0000", "hub_error=config"),
])
def test_cli_refuses_unsafe_or_incomplete_config(args, secret_value, expected):
    proc = _cli(args, secret_value)
    out, _ = proc.communicate(timeout=20)
    assert proc.returncode == 2 and expected in out
    if secret_value:
        assert secret_value not in out
