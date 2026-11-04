"""Tests for the S1/S5 harness itself.

They exercise configuration, gates, I/O helpers (real loopback sockets
and HTTP servers) and the PASS/FAIL classifiers over recorded timelines.
The runtime's election/liveness behavior is not simulated here; it is
covered by tests/test_master_liveness_probe.py and by real harness runs.
"""

import importlib.util
import json
import socket
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("s1s5_harness", HERE / "s1s5_harness.py")
h = importlib.util.module_from_spec(_spec)
sys.modules["s1s5_harness"] = h
_spec.loader.exec_module(h)

IDS = ["NODE-A", "NODE-B", "NODE-C"]


def base_config():
    return json.loads((HERE / "topology-loopback.json").read_text(encoding="utf-8"))


def topo_b(win="10.0.0.5", phone="10.0.0.8"):
    data = json.loads((HERE / "topology-b.example.json").read_text(encoding="utf-8"))
    text = json.dumps(data).replace("<WINDOWS_LAN_IP>", win).replace("<PHONE_LAN_IP>", phone)
    return json.loads(text)


# --------------------------------------------------------------------- config

def test_loopback_config_is_valid():
    cfg = h.parse_config(base_config())
    assert cfg.node_ids == IDS
    assert cfg.initial_master == "NODE-A"
    assert cfg.single_host
    assert cfg.min_free_mb == 2048


def test_topology_b_example_rejects_unreplaced_placeholders():
    data = json.loads((HERE / "topology-b.example.json").read_text(encoding="utf-8"))
    with pytest.raises(h.ConfigError, match="placeholder"):
        h.parse_config(data)


def test_topology_b_with_addresses_is_valid():
    cfg = h.parse_config(topo_b())
    assert not cfg.single_host
    assert cfg.hub.url == "http://10.0.0.5:8500"


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(cluster_size=1), "cluster_size"),
    (lambda d: d.update(cluster_size=True), "cluster_size"),
    (lambda d: d["hub"].update(port=8600), "hub.port"),
    (lambda d: d["nodes"].pop(), "exactly 3"),
    (lambda d: d["nodes"][1].update(initial_role="MASTER"), "exactly one"),
    (lambda d: d["nodes"][1].update(node_id="NODE-A"), "unique"),
    (lambda d: d["nodes"][1].update(web_port=8081), "used twice"),
    (lambda d: d["nodes"][2].update(tcp_port=8500), "used twice"),
    (lambda d: d.update(min_free_mb=1024), "authorization"),
    (lambda d: d.update(timing={"s1_window_s": 30}), "s1_window_s"),
    (lambda d: d.update(timing={"unknown": 1}), "unknown timing"),
    (lambda d: d.update(expected_core_git_blob="abc"), "40 hex"),
    (lambda d: d.update(expected_core_sha256="0" * 64), "not portable"),
])
def test_invalid_configs_are_rejected(mutate, message):
    data = base_config()
    mutate(data)
    with pytest.raises(h.ConfigError, match=message):
        h.parse_config(data)


def test_multi_host_rejects_loopback_hub():
    data = topo_b()
    data["hub"]["host"] = "127.0.0.1"
    with pytest.raises(h.ConfigError, match="loopback"):
        h.parse_config(data)


def test_multi_host_rejects_loopback_member():
    data = topo_b()
    data["nodes"][0]["host"] = "127.0.0.1"
    with pytest.raises(h.ConfigError, match="loopback"):
        h.parse_config(data)


def test_public_config_has_no_secret_field():
    cfg = h.parse_config(base_config())
    assert "secret" not in json.dumps(cfg.public_dict()).lower()


# ---------------------------------------------------------------------- gates

def test_memory_gate_blocks_below_2048():
    assert h.memory_gate(2047.9, 2048)["status"] == h.BLOCKED
    assert h.memory_gate(2048.0, 2048)["status"] == h.PASS
    assert h.memory_gate(None, 2048)["reason"] == "memory_unmeasurable"


def test_available_memory_is_measurable_on_this_host():
    assert h.available_memory_mb() is not None


def test_process_rss_of_self_is_measurable():
    import os
    rss = h.process_rss_mb(os.getpid())
    assert rss is not None and rss > 1


def test_secret_gate_never_echoes_secret():
    secret = "s3cr3t-value-for-test-0123456789"
    report = h.secret_gate(secret)
    assert report["status"] == h.PASS
    assert secret not in json.dumps(report)
    assert h.secret_gate("")["status"] == h.BLOCKED
    assert h.secret_gate("short")["reason"] == "NEXUS_SECRET_KEY_too_short"


def test_preflight_blocks_on_memory_and_secret_without_starting_anything():
    cfg = h.parse_config(base_config())
    report = h.preflight(cfg, [], include_hub=False, secret="", available_mb=600,
                         check_clock=False)
    assert report["status"] == h.BLOCKED
    assert {"memory", "secret"} <= set(report["blocked_checks"])


def test_runtime_integrity_reports_core_hash():
    cfg = h.parse_config(base_config())
    report = h.runtime_integrity(cfg)
    assert "nexus_distributed_core.py" in report["sha256_raw_bytes"]
    assert report["missing"] == []


def test_runtime_integrity_blocks_on_hash_mismatch():
    data = base_config()
    data["expected_core_git_blob"] = "0" * 40
    report = h.runtime_integrity(h.parse_config(data))
    assert "core_git_blob_mismatch" in report["reasons"]


def test_git_blob_matches_git_and_ignores_crlf(tmp_path):
    lf = tmp_path / "lf.py"
    crlf = tmp_path / "crlf.py"
    lf.write_bytes(b"a = 1\nb = 2\n")
    crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert h.git_blob_id(lf) == h.git_blob_id(crlf)
    # Known git blob id of "a = 1\nb = 2\n" computed independently.
    import hashlib
    data = b"a = 1\nb = 2\n"
    assert h.git_blob_id(lf) == hashlib.sha1(b"blob 12\0" + data).hexdigest()


def test_runtime_core_matches_reference_commit_blob():
    report = h.runtime_integrity(h.parse_config(base_config()))
    assert report["git_blob"]["nexus_distributed_core.py"] == "eb8a48da88a75f9d58c954f8afeed86c2af27f93"


def test_port_in_use_detects_listener():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert h.port_in_use(port)


def test_clock_single_host_is_not_applicable():
    report = h.clock_check(True, servers=())
    assert report["status"] == h.PASS


def test_clock_multi_host_without_ntp_is_blocked():
    report = h.clock_check(False, servers=())
    assert report["status"] == h.BLOCKED


def test_scrub_removes_secret():
    assert h.scrub("x=abc123secret y", "abc123secret") == "x=[REDACTED] y"


# ------------------------------------------------------------- real loopback I/O

class _StatusHandler(BaseHTTPRequestHandler):
    payload = {}

    def log_message(self, *_):
        pass

    def do_GET(self):
        body = json.dumps(self.payload.get(self.path, {})).encode()
        self.send_response(200 if self.path in self.payload else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def status_server():
    class Handler(_StatusHandler):
        payload = {
            "/status": {"status": "OPERATIONAL", "node_id": "NODE-A", "role": "MASTER", "height": 0},
            "/peers": {"NODE-A": {"role": "MASTER", "ip": "127.0.0.1"}},
        }
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_observe_node_and_hub_parse_real_http(status_server):
    node = h.NodeSpec("NODE-A", "127.0.0.1", status_server, 1, "MASTER", True)
    obs = h.observe_node(node, 2.0)
    assert obs == {"ok": True, "role": "MASTER", "node_id": "NODE-A", "height": 0}
    hub = h.observe_hub(h.HubSpec("127.0.0.1", status_server, True), 2.0)
    assert hub["ok"] and hub["roles"] == {"NODE-A": "MASTER"}


def test_observe_node_unreachable():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    obs = h.observe_node(h.NodeSpec("X", "127.0.0.1", port, 1, "MASTER", True), 1.0)
    assert obs["ok"] is False and obs["error"]


def _tcp_server(behavior):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        with conn:
            header = conn.recv(4)
            size = struct.unpack("!I", header)[0]
            data = b""
            while len(data) < size:
                data += conn.recv(size - len(data))
            behavior(conn, json.loads(data))
        srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1]


def test_qs_probe_refused_when_node_closes():
    port = _tcp_server(lambda conn, msg: None)
    assert h.qs_c01_probe("127.0.0.1", port) == "REFUSED_CLOSED"


def test_qs_probe_detects_accepted_sync():
    def reply(conn, msg):
        assert msg["type"] == "STATE_SUMMARY"
        conn.sendall(h._frame({"type": "SYNC_BATCH", "from_height": 0, "blocks": []}))
    port = _tcp_server(reply)
    assert h.qs_c01_probe("127.0.0.1", port) == "ACCEPTED"


def test_qs_probe_uses_runtime_wire_format():
    root = h.DEFAULT_RUNTIME_ROOT
    sys.path.insert(0, str(root))
    try:
        import nexus_transport
    finally:
        sys.path.remove(str(root))
    msg = {"type": "STATE_SUMMARY", "payload": {"height": 0}}
    assert h._frame(msg) == nexus_transport.encode_message(msg)


def test_qs_probe_unreachable():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert h.qs_c01_probe("127.0.0.1", port, timeout=1) == "UNREACHABLE"


def test_parse_log_events_reads_runtime_format():
    text = (
        "2026-11-03 14:00:00,250 INFO core_ready node=NODE-B role=FOLLOWER\n"
        "2026-11-03 14:00:20,000 WARNING master_missing node=NODE-B seconds=15.2\n"
        "random line\n"
    )
    events = h.parse_log_events(text, "NODE-B")
    assert [e["event"] for e in events] == ["core_ready", "master_missing"]
    assert events[1]["epoch"] - events[0]["epoch"] == pytest.approx(19.75)
    assert h.count_events(events, after=events[1]["epoch"]) == {"master_missing": 1}


# -------------------------------------------------------------- classifiers

def sample(t, roles, hub_roles=None, down=()):
    nodes = {}
    for n in IDS:
        if n in down:
            nodes[n] = {"ok": False, "error": "URLError:ConnectionRefusedError"}
        else:
            nodes[n] = {"ok": True, "role": roles[n], "node_id": n}
    hub = {"ok": True, "roles": dict(hub_roles if hub_roles is not None else roles)}
    return {"t": float(t), "nodes": nodes, "hub": hub}


STABLE = {"NODE-A": "MASTER", "NODE-B": "FOLLOWER", "NODE-C": "FOLLOWER"}
QS_OK = {n: "REFUSED_CLOSED" for n in IDS}


def s1_timeline(n=120):
    return [sample(t, STABLE) for t in range(n)]


def classify_s1(samples, logs=None, qs=QS_OK):
    timing = h.Timing()
    return h.classify_stable_master(samples, IDS, "NODE-A", timing, start=0, end=len(samples) - 1,
                                    log_counts=logs or {}, qs_results=qs)


def test_s1_pass_on_stable_timeline():
    result = classify_s1(s1_timeline())
    assert result["verdict"] == h.PASS, result


def test_s1_fail_when_follower_reports_master():
    samples = s1_timeline()
    samples[60] = sample(60, {**STABLE, "NODE-C": "MASTER"})
    result = classify_s1(samples)
    assert result["verdict"] == h.FAIL
    assert "follower_promoted_while_master_alive" in result["reasons"]


def test_s1_fail_on_master_missing_log():
    result = classify_s1(s1_timeline(), logs={"master_missing": 1})
    assert "log_master_missing" in result["reasons"]


def test_s1_fail_on_hub_divergence():
    samples = s1_timeline()
    samples[10] = sample(10, STABLE, hub_roles={**STABLE, "NODE-B": "MASTER"})
    assert "hub_role_divergence" in classify_s1(samples)["reasons"]


def test_s1_fail_on_observation_gap():
    samples = s1_timeline()
    for t in range(40, 55):
        samples[t] = sample(t, STABLE, down=("NODE-B",))
    assert "observability_gap" in classify_s1(samples)["reasons"]


def test_s1_fail_when_sync_accepted_with_n3():
    result = classify_s1(s1_timeline(), qs={**QS_OK, "NODE-A": "ACCEPTED"})
    assert "distributed_sync_accepted_with_n3" in result["reasons"]


def test_s1_fail_when_qs_probe_inconclusive():
    result = classify_s1(s1_timeline(), qs={**QS_OK, "NODE-B": "UNREACHABLE"})
    assert "qs_c01_probe_inconclusive" in result["reasons"]


def test_s1_fail_on_identity_mismatch():
    samples = s1_timeline()
    samples[5]["nodes"]["NODE-B"]["node_id"] = "NODE-X"
    assert "identity_mismatch" in classify_s1(samples)["reasons"]


def test_s1_fail_on_state_write_with_n3():
    assert "log_sync_batch_applied_with_n3" in classify_s1(
        s1_timeline(), logs={"sync_batch_applied": 1})["reasons"]


def test_s1_empty_is_fail():
    assert classify_s1([])["verdict"] == h.FAIL


def test_expected_candidate_matches_runtime_rule():
    assert h.expected_candidate(IDS, "NODE-A") == "NODE-C"
    assert h.expected_candidate(IDS, "NODE-C") == "NODE-B"


AFTER = {"NODE-B": "FOLLOWER", "NODE-C": "MASTER"}


def s5_timeline(promote_at=25, end=90, reap_at=32, concurrent=()):
    out = []
    for t in range(0, end + 1):
        roles = {"NODE-A": None, "NODE-B": "FOLLOWER",
                 "NODE-C": "MASTER" if t >= promote_at else "FOLLOWER"}
        if t in concurrent:
            roles["NODE-B"] = "MASTER"
        hub = {"NODE-B": roles["NODE-B"], "NODE-C": roles["NODE-C"]}
        if t < reap_at:
            hub["NODE-A"] = "MASTER"
        out.append(sample(t, roles, hub_roles=hub, down=("NODE-A",)))
    return out


def classify_s5(post, kill_info=None, logs=None, qs="REFUSED_CLOSED"):
    return h.classify_failover(post, IDS, "NODE-A", h.Timing(), t_kill=0.0,
                               kill_info=kill_info or {"exit_code": 1},
                               log_events_after_kill=logs or {}, qs_new_master=qs)


def test_s5_pass_on_expected_failover():
    result = classify_s5(s5_timeline())
    assert result["verdict"] == h.PASS, result
    assert result["metrics"]["promotion_delay_s"] == 25
    assert result["metrics"]["expected_candidate"] == "NODE-C"


def test_s5_fail_without_promotion():
    post = [sample(t, {"NODE-A": None, "NODE-B": "FOLLOWER", "NODE-C": "FOLLOWER"},
                   hub_roles={"NODE-B": "FOLLOWER", "NODE-C": "FOLLOWER"}, down=("NODE-A",))
            for t in range(91)]
    assert "no_promotion_within_deadline" in classify_s5(post)["reasons"]


def test_s5_fail_on_unexpected_candidate():
    post = s5_timeline()
    for s in post:
        if s["t"] >= 25:
            s["nodes"]["NODE-B"]["role"] = "MASTER"
            s["nodes"]["NODE-C"]["role"] = "FOLLOWER"
            s["hub"]["roles"].update({"NODE-B": "MASTER", "NODE-C": "FOLLOWER"})
    reasons = classify_s5(post)["reasons"]
    assert "unexpected_candidate" in reasons


def test_s5_fail_on_premature_promotion():
    assert "premature_promotion" in classify_s5(s5_timeline(promote_at=3))["reasons"]


def test_s5_fail_on_persistent_concurrent_master():
    post = s5_timeline(concurrent=range(26, 45))
    assert "persistent_concurrent_master" in classify_s5(post)["reasons"]


def test_s5_transient_concurrent_master_is_warning():
    result = classify_s5(s5_timeline(concurrent=(26,)))
    assert result["verdict"] == h.PASS
    assert "transient_concurrent_master" in result["warnings"]


def test_s5_fail_when_master_not_stopped():
    assert "master_not_stopped" in classify_s5(s5_timeline(), kill_info={"exit_code": None})["reasons"]


def test_s5_fail_when_failed_master_still_serves():
    post = s5_timeline()
    post[10]["nodes"]["NODE-A"] = {"ok": True, "role": "MASTER", "node_id": "NODE-A"}
    assert "failed_master_still_serving" in classify_s5(post)["reasons"]


def test_s5_fail_when_hub_does_not_reap():
    assert "hub_failed_master_not_reaped" in classify_s5(s5_timeline(reap_at=10**6))["reasons"]


def test_s5_fail_when_not_held_long_enough():
    assert "not_converged" in classify_s5(s5_timeline(promote_at=25, end=40))["reasons"]


def test_s5_fail_when_new_master_accepts_sync():
    assert "distributed_sync_accepted_with_n3" in classify_s5(s5_timeline(), qs="ACCEPTED")["reasons"]


def test_s5_fail_on_state_write_after_kill():
    assert "state_written_with_n3" in classify_s5(s5_timeline(), logs={"event_persisted": 1})["reasons"]


# ------------------------------------------------------------- non-destructive

def test_harness_source_has_no_destructive_operations():
    source = (HERE / "s1s5_harness.py").read_text(encoding="utf-8")
    for forbidden in ("rmtree", "os.remove(", ".unlink(", "os.rmdir", "git reset",
                      "git clean", "git checkout", "git push", "git commit",
                      "netsh", "New-NetFirewallRule", "w32tm", "taskkill", "os.kill("):
        assert forbidden not in source, forbidden


def test_child_env_passes_secret_only_through_environment():
    cfg = h.parse_config(base_config())
    node = cfg.node("NODE-A")
    cmd = h.node_command(cfg, node)
    assert not any("secret" in part.lower() for part in cmd)
    env = h.child_env(cfg, "x" * 32, Path("db"))
    assert env["NEXUS_SECRET_KEY"] == "x" * 32
    assert env["NEXUS_CLUSTER_SIZE"] == "3"
    assert "-B" in cmd  # no __pycache__ written into the runtime tree
