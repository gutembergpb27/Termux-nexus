"""Tests for the S1/S5 harness itself (W06).

Three layers:
1. configuration, gates and I/O helpers (real loopback sockets/HTTP);
2. PASS/FAIL/BLOCKED classifiers over recorded timelines;
3. the orchestrator end to end, driving small stand-in processes
   (stub hub and stub node written below, bound to 127.0.0.1 only).

Layer 3 validates the harness's process management, shutdown, evidence
and secret handling. It is NOT an S1/S5 run of the Nexus runtime: the
runtime's election/liveness behavior is covered by
tests/test_master_liveness_probe.py and by real harness runs.
"""

import importlib.util
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("s1s5_harness", HERE / "s1s5_harness.py")
h = importlib.util.module_from_spec(_spec)
sys.modules["s1s5_harness"] = h
_spec.loader.exec_module(h)

IDS = ["NODE-A", "NODE-B", "NODE-C"]
SECRET = "w06-test-secret-" + "f3a9" * 8


def base_config():
    return json.loads((HERE / "topology-loopback.json").read_text(encoding="utf-8"))


def topo_b(win="10.0.0.5", phone="10.0.0.8"):
    text = (HERE / "topology-b.example.json").read_text(encoding="utf-8")
    return json.loads(text.replace("<WINDOWS_LAN_IP>", win).replace("<PHONE_LAN_IP>", phone))


# ======================================================================
# 1. configuration and gates
# ======================================================================

def test_loopback_config_is_valid():
    cfg = h.parse_config(base_config())
    assert cfg.node_ids == IDS
    assert cfg.initial_master == "NODE-A"
    assert cfg.single_host
    assert cfg.min_free_mb == 2048


def test_examples_reject_unreplaced_placeholders():
    for name in ("topology-b.example.json", "topology-b-phone.example.json"):
        data = json.loads((HERE / name).read_text(encoding="utf-8"))
        with pytest.raises(h.ConfigError, match="placeholder"):
            h.parse_config(data)


def test_topology_b_with_addresses_is_valid():
    cfg = h.parse_config(topo_b())
    assert not cfg.single_host
    assert cfg.hub.url == "http://10.0.0.5:8500"
    phone = json.loads((HERE / "topology-b-phone.example.json").read_text(encoding="utf-8")
                       .replace("<WINDOWS_LAN_IP>", "10.0.0.5").replace("<PHONE_LAN_IP>", "10.0.0.8"))
    assert h.parse_config(phone).local_node_ids == ["NODE-C"]


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(cluster_size=1), "cluster_size"),
    (lambda d: d.update(cluster_size=True), "cluster_size"),
    (lambda d: d["hub"].update(port=8600), "hub.port"),
    (lambda d: d["hub"].update(host="bad host!"), "valid host"),
    (lambda d: d["nodes"].pop(), "exactly 3"),
    (lambda d: d["nodes"][1].update(initial_role="MASTER"), "exactly one"),
    (lambda d: d["nodes"][1].update(initial_role="LEADER"), "initial_role"),
    (lambda d: d["nodes"][1].update(node_id="NODE-A"), "unique"),
    (lambda d: d["nodes"][1].update(node_id="../x"), "node_id"),
    (lambda d: d["nodes"][1].update(web_port=8081), "used twice"),
    (lambda d: d["nodes"][2].update(tcp_port=8500), "used twice"),
    (lambda d: d["nodes"][2].update(tcp_port=70000), "out of range"),
    (lambda d: d["nodes"][2].update(tcp_port="9093"), "integer"),
    (lambda d: [n.update(local=False) for n in d["nodes"]], "loopback"),
    (lambda d: d.update(min_free_mb=1024), "authorization"),
    (lambda d: d.update(timing={"s1_window_s": 30}), "s1_window_s"),
    (lambda d: d.update(timing={"min_availability": 0.9}), "tightened"),
    (lambda d: d.update(timing={"min_promotion_delay_s": 5}), "tightened"),
    (lambda d: d.update(timing={"max_observation_gap_s": 30}), "tightened"),
    (lambda d: d.update(timing={"sample_interval_s": 2}), "tightened"),
    (lambda d: d.update(timing={"s5_promotion_deadline_s": 120}), "tightened"),
    (lambda d: d.update(timing={"s5_hold_s": 10}), "tightened"),
    (lambda d: d.update(timing={"concurrent_master_grace_s": 10}), "unknown timing"),
    (lambda d: d.update(timing={"s1_window_s": True}), "number"),
    (lambda d: d.update(expected_core_git_blob="abc"), "40 hex"),
    (lambda d: d.update(expected_core_sha256="0" * 64), "not portable"),
])
def test_invalid_configs_are_rejected(mutate, message):
    data = base_config()
    mutate(data)
    with pytest.raises(h.ConfigError, match=message):
        h.parse_config(data)


def test_stricter_timing_is_accepted():
    data = base_config()
    data["timing"] = {"min_availability": 0.99, "s1_window_s": 300, "max_observation_gap_s": 5}
    assert h.parse_config(data).timing.min_availability == 0.99


def test_multi_host_rejects_loopback_hub_and_member():
    data = topo_b()
    data["hub"]["host"] = "127.0.0.1"
    with pytest.raises(h.ConfigError, match="loopback"):
        h.parse_config(data)
    data = topo_b()
    data["nodes"][0]["host"] = "127.0.0.1"
    with pytest.raises(h.ConfigError, match="loopback"):
        h.parse_config(data)


def test_config_with_utf8_bom_loads(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(base_config()).encode())
    assert h.load_config(path).node_ids == IDS


def test_public_config_has_no_secret_field():
    cfg = h.parse_config(base_config())
    assert "secret" not in json.dumps(cfg.public_dict()).lower()


def test_memory_gate_blocks_below_2048():
    assert h.memory_gate(2047.9, 2048)["status"] == h.BLOCKED
    assert h.memory_gate(2048.0, 2048)["status"] == h.PASS
    assert h.memory_gate(None, 2048)["reason"] == "memory_unmeasurable"


def test_memory_is_measurable_on_this_host():
    assert h.available_memory_mb() is not None
    assert (h.process_rss_mb(os.getpid()) or 0) > 1


def test_secret_gate_never_echoes_secret():
    report = h.secret_gate(SECRET)
    assert report["status"] == h.PASS and SECRET not in json.dumps(report)
    assert h.secret_gate("")["status"] == h.BLOCKED
    assert h.secret_gate("short")["reason"] == "NEXUS_SECRET_KEY_too_short"


def test_scrub_removes_raw_and_json_escaped_secret():
    tricky = 'abc"def\\ghi-0123456789'
    blob = json.dumps({"x": f"pre {tricky} post"})
    assert tricky not in h.scrub(blob, tricky)
    assert json.dumps(tricky)[1:-1] not in h.scrub(blob, tricky)
    assert "[REDACTED]" in h.scrub(f"k={tricky}", tricky)


def test_safe_error_scrubs_exception_text():
    msg = h.safe_error(RuntimeError(f"failed with {SECRET}"), SECRET)
    assert SECRET not in msg and "[REDACTED]" in msg


# --- local identity: evidence must be publishable as written ---------------

FAKE_HOST = "DESKTOP-ALICE42"


@pytest.fixture
def fake_identity(tmp_path, monkeypatch):
    home = tmp_path / "home" / "alice"
    temp = home / "AppData" / "Local" / "Temp"
    temp.mkdir(parents=True)
    monkeypatch.setattr(h.tempfile, "gettempdir", lambda: str(temp))
    monkeypatch.setattr(h.Path, "home", classmethod(lambda cls: cls(home)))
    monkeypatch.setattr(h.socket, "gethostname", lambda: FAKE_HOST)
    return home, temp


def test_host_metadata_never_records_hostname(fake_identity):
    meta = h.host_metadata()
    assert set(meta) == {"platform", "python", "hostname"}
    assert meta["hostname"] == h.REDACTED_HOSTNAME
    assert FAKE_HOST not in json.dumps(meta)


def test_public_path_replaces_temp_and_home_prefixes(fake_identity):
    home, temp = fake_identity
    assert h.public_path(temp / "nexus-s1s5-x") == h.REDACTED_TEMP + os.sep + "nexus-s1s5-x"
    assert h.public_path(home / "repo") == h.REDACTED_HOME + os.sep + "repo"
    assert h.public_path(home) == h.REDACTED_HOME
    # neither a sibling with the same prefix nor an unrelated path is touched
    assert h.public_path(str(home) + "ish") == str(home) + "ish"
    assert h.public_path(home.parent / "bob") == str(home.parent / "bob")


def test_scrub_redacts_local_identity_in_json_and_logs(fake_identity):
    home, temp = fake_identity
    doc = {"work_dir": str(temp / "run-1"), "root": str(home / "repo"),
           "posix": (home / "x").as_posix(), "log": f"node up on {FAKE_HOST.lower()}:8000"}
    out = h.scrub(json.dumps(doc), None)
    for raw in (str(temp), str(home), home.as_posix(), json.dumps(str(home))[1:-1]):
        assert raw not in out
    assert FAKE_HOST.lower() not in out.lower()
    back = json.loads(out)
    assert back["work_dir"].startswith(h.REDACTED_TEMP)
    assert back["root"].startswith(h.REDACTED_HOME)
    assert back["log"] == f"node up on {h.REDACTED_HOSTNAME}:8000"


def test_scrub_keeps_generic_hostnames(monkeypatch):
    monkeypatch.setattr(h.socket, "gethostname", lambda: "localhost")
    assert h.scrub("connect localhost:80", None) == "connect localhost:80"


def test_scrub_removes_secret_before_hostname(fake_identity):
    secret = FAKE_HOST + "-" + "k" * 16
    out = h.scrub(f"s={secret}", secret)
    assert out == "s=[REDACTED]"


def test_preflight_blocks_without_starting_anything():
    cfg = h.parse_config(base_config())
    report = h.preflight(cfg, [], include_hub=False, secret="", available_mb=600,
                         check_clock=False)
    assert report["status"] == h.BLOCKED
    assert {"memory", "secret", "exposure"} <= set(report["blocked_checks"])


def test_exposure_audit_finds_runtime_wildcard_binds():
    cfg = h.parse_config(base_config())
    report = h.exposure_audit(cfg, accepted=False)
    files = {b["file"] for b in report["wildcard_binds"]}
    assert files == {"nexus_rendezvous.py", "nexus_distributed_core.py", "web_panel.py"}
    assert report["status"] == h.BLOCKED
    assert h.exposure_audit(cfg, accepted=True)["status"] == h.PASS


def test_runtime_integrity_matches_reference_blob():
    report = h.runtime_integrity(h.parse_config(base_config()))
    assert report["missing"] == []
    assert report["git_blob"]["nexus_distributed_core.py"] == "eb8a48da88a75f9d58c954f8afeed86c2af27f93"
    data = base_config()
    data["expected_core_git_blob"] = "0" * 40
    assert "core_git_blob_mismatch" in h.runtime_integrity(h.parse_config(data))["reasons"]


def test_git_blob_ignores_crlf(tmp_path):
    import hashlib
    (tmp_path / "lf").write_bytes(b"a = 1\nb = 2\n")
    (tmp_path / "crlf").write_bytes(b"a = 1\r\nb = 2\r\n")
    expected = hashlib.sha1(b"blob 12\0" + b"a = 1\nb = 2\n").hexdigest()
    assert h.git_blob_id(tmp_path / "lf") == h.git_blob_id(tmp_path / "crlf") == expected


def test_port_in_use_detects_listener():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        assert h.port_in_use(srv.getsockname()[1])


def test_port_in_use_detects_listener_with_full_backlog():
    # Regression (W06): connect is refused when the backlog is full and a
    # plain wildcard bind succeeds on Windows; the port must still count as busy.
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(0)
        port = srv.getsockname()[1]
        fillers = []
        for _ in range(4):
            s = socket.socket()
            s.settimeout(0.3)
            s.connect_ex(("127.0.0.1", port))
            fillers.append(s)
        try:
            assert h.port_in_use(port)
        finally:
            for s in fillers:
                s.close()


def test_port_in_use_detects_bound_but_not_listening():
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        assert h.port_in_use(srv.getsockname()[1])


def test_free_port_is_reported_free():
    assert not h.port_in_use(_free_port())


def test_clock_rules():
    assert h.clock_check(True, servers=())["status"] == h.PASS
    assert h.clock_check(False, servers=())["status"] == h.BLOCKED


# ======================================================================
# 1b. I/O helpers over real loopback
# ======================================================================

@pytest.fixture
def status_server():
    class Handler(BaseHTTPRequestHandler):
        payload = {
            "/status": {"status": "OPERATIONAL", "node_id": "NODE-A", "role": "MASTER", "height": 0},
            "/peers": {"NODE-A": {"role": "MASTER", "ip": "127.0.0.1"}},
        }

        def log_message(self, *_):
            pass

        def do_GET(self):
            body = json.dumps(self.payload.get(self.path, {})).encode()
            self.send_response(200 if self.path in self.payload else 404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_observe_node_and_hub_parse_real_http(status_server):
    node = h.NodeSpec("NODE-A", "127.0.0.1", status_server, 1, "MASTER", True)
    assert h.observe_node(node, 2.0) == {"ok": True, "role": "MASTER", "node_id": "NODE-A", "height": 0}
    hub = h.observe_hub(h.HubSpec("127.0.0.1", status_server, True), 2.0)
    assert hub["ok"] and hub["roles"] == {"NODE-A": "MASTER"}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_observe_node_unreachable():
    obs = h.observe_node(h.NodeSpec("X", "127.0.0.1", _free_port(), 1, "MASTER", True), 1.0)
    assert obs["ok"] is False and obs["error"]


def _tcp_server(behavior):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        with conn:
            size = struct.unpack("!I", conn.recv(4))[0]
            data = b""
            while len(data) < size:
                data += conn.recv(size - len(data))
            behavior(conn, json.loads(data))
        srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1]


def test_qs_probe_outcomes():
    assert h.qs_c01_probe("127.0.0.1", _tcp_server(lambda c, m: None)) == "REFUSED_CLOSED"

    def accept(conn, msg):
        assert msg["type"] == "STATE_SUMMARY"
        conn.sendall(h._frame({"type": "SYNC_BATCH", "from_height": 0, "blocks": []}))
    assert h.qs_c01_probe("127.0.0.1", _tcp_server(accept)) == "ACCEPTED"

    def garbage(conn, msg):
        conn.sendall(struct.pack("!I", 3) + b"{x}")
    assert h.qs_c01_probe("127.0.0.1", _tcp_server(garbage)) == "UNEXPECTED_RESPONSE"
    assert h.qs_c01_probe("127.0.0.1", _free_port(), timeout=1) == "UNREACHABLE"


def test_qs_probe_uses_runtime_wire_format():
    root = h.DEFAULT_RUNTIME_ROOT
    sys.path.insert(0, str(root))
    try:
        import nexus_transport
    finally:
        sys.path.remove(str(root))
    msg = {"type": "STATE_SUMMARY", "payload": {"height": 0}}
    assert h._frame(msg) == nexus_transport.encode_message(msg)


def test_qs_corroboration_reads_runtime_log_line():
    text = ("2026-11-03 14:00:01,000 WARNING distributed_sync_blocked node=NODE-B "
            "operation=state_summary reason=quorum_commit_not_implemented\n")
    events = h.parse_log_events(text, "NODE-B")
    after = events[0]["epoch"] - 0.5
    assert h.qs_log_corroboration(events, ["NODE-B", "NODE-C"], after) == {"NODE-B": True, "NODE-C": False}


def test_parse_log_events_reads_runtime_format():
    text = ("2026-11-03 14:00:00,250 INFO core_ready node=NODE-B role=FOLLOWER\n"
            "2026-11-03 14:00:20,000 WARNING master_missing node=NODE-B seconds=15.2\n"
            "random line\n")
    events = h.parse_log_events(text, "NODE-B")
    assert [e["event"] for e in events] == ["core_ready", "master_missing"]
    assert events[1]["epoch"] - events[0]["epoch"] == pytest.approx(19.75)
    assert h.count_events(events, after=events[1]["epoch"]) == {"master_missing": 1}
    assert h.count_events(events, nodes=["NODE-X"]) == {}


# ======================================================================
# 2. classifiers
# ======================================================================

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
CORR_OK = {n: True for n in IDS}


def classify_s1(samples, logs=None, qs=QS_OK, corr=CORR_OK, log_nodes=IDS):
    return h.classify_stable_master(samples, IDS, "NODE-A", h.Timing(), start=0,
                                    end=max(len(samples) - 1, 0), log_counts=logs or {},
                                    qs_results=qs, qs_corroboration=corr, log_nodes=log_nodes)


def s1_timeline(n=120):
    return [sample(t, STABLE) for t in range(n)]


def test_verdict_semantics():
    assert h.verdict_for([]) == h.PASS
    assert h.verdict_for(["observability_gap"]) == h.BLOCKED
    assert h.verdict_for(["baseline:observability_gap"]) == h.BLOCKED
    assert h.verdict_for(["observability_gap", "multiple_masters_observed"]) == h.FAIL


def test_s1_pass_on_stable_timeline():
    result = classify_s1(s1_timeline())
    assert result["verdict"] == h.PASS, result


def test_s1_follower_promotion_is_fail():
    samples = s1_timeline()
    samples[60] = sample(60, {**STABLE, "NODE-C": "MASTER"})
    result = classify_s1(samples)
    assert result["verdict"] == h.FAIL
    assert {"follower_promoted_while_master_alive", "multiple_masters_observed"} <= set(result["reasons"])


def test_s1_single_sample_dual_master_is_fail():
    samples = s1_timeline()
    samples[5] = sample(5, {**STABLE, "NODE-B": "MASTER"})
    assert classify_s1(samples)["verdict"] == h.FAIL


def test_s1_master_demoted_is_fail():
    samples = s1_timeline()
    samples[7] = sample(7, {**STABLE, "NODE-A": "FOLLOWER"})
    assert "master_role_lost" in classify_s1(samples)["reasons"]


@pytest.mark.parametrize("logs, reason", [
    ({"master_missing": 1}, "log_master_missing"),
    ({"leadership_promoted": 1}, "log_leadership_promoted"),
    ({"leadership_promotion_started": 1}, "log_leadership_promotion_started"),
    ({"sync_batch_applied": 1}, "log_sync_batch_applied_with_n3"),
    ({"event_persisted": 1}, "log_event_persisted_with_n3"),
])
def test_s1_log_violations_are_fail(logs, reason):
    result = classify_s1(s1_timeline(), logs=logs)
    assert result["verdict"] == h.FAIL and reason in result["reasons"]


def test_s1_hub_divergence_is_fail():
    samples = s1_timeline()
    samples[10] = sample(10, STABLE, hub_roles={**STABLE, "NODE-B": "MASTER"})
    assert "hub_role_divergence" in classify_s1(samples)["reasons"]


def test_s1_observation_gap_is_blocked_not_fail():
    samples = s1_timeline()
    for t in range(40, 55):
        samples[t] = sample(t, STABLE, down=("NODE-B",))
    result = classify_s1(samples)
    assert result["verdict"] == h.BLOCKED and result["reasons"] == ["observability_gap"]


def test_s1_qs_outcomes():
    assert classify_s1(s1_timeline(), qs={**QS_OK, "NODE-A": "ACCEPTED"})["verdict"] == h.FAIL
    assert classify_s1(s1_timeline(), qs={**QS_OK, "NODE-A": "UNEXPECTED_RESPONSE"})["verdict"] == h.FAIL
    assert classify_s1(s1_timeline(), qs={**QS_OK, "NODE-B": "UNREACHABLE"})["verdict"] == h.BLOCKED
    not_corr = classify_s1(s1_timeline(), corr={**CORR_OK, "NODE-C": False})
    assert not_corr["verdict"] == h.BLOCKED
    assert "qs_c01_not_corroborated_in_log" in not_corr["reasons"]


def test_s1_identity_mismatch_is_fail():
    samples = s1_timeline()
    samples[5]["nodes"]["NODE-B"]["node_id"] = "NODE-X"
    assert "identity_mismatch" in classify_s1(samples)["reasons"]
    samples = s1_timeline()
    samples[5]["nodes"]["NODE-B"]["node_id"] = None
    assert "identity_mismatch" in classify_s1(samples)["reasons"]


def test_s1_partial_log_coverage_is_warning():
    result = classify_s1(s1_timeline(), corr={"NODE-A": True, "NODE-B": True},
                         log_nodes=["NODE-A", "NODE-B"])
    assert result["verdict"] == h.PASS
    assert "log_coverage_partial:NODE-C" in result["warnings"]


def test_s1_empty_is_blocked():
    assert classify_s1([])["verdict"] == h.BLOCKED


def test_expected_candidate_matches_runtime_rule():
    assert h.expected_candidate(IDS, "NODE-A") == "NODE-C"
    assert h.expected_candidate(IDS, "NODE-C") == "NODE-B"


def s5_timeline(promote_at=25, end=90, reap_at=32, extra_master=()):
    out = []
    for t in range(0, end + 1):
        roles = {"NODE-A": None, "NODE-B": "FOLLOWER",
                 "NODE-C": "MASTER" if t >= promote_at else "FOLLOWER"}
        if t in extra_master:
            roles["NODE-B"] = "MASTER"
        hub = {"NODE-B": roles["NODE-B"], "NODE-C": roles["NODE-C"]}
        if t < reap_at:
            hub["NODE-A"] = "MASTER"
        out.append(sample(t, roles, hub_roles=hub, down=("NODE-A",)))
    return out


def classify_s5(post, kill_info=None, logs=None, qs="REFUSED_CLOSED", corr=None):
    return h.classify_failover(post, IDS, "NODE-A", h.Timing(), t_kill=0.0,
                               kill_info=kill_info or {"exit_code": 1},
                               log_events_after_kill=logs or {}, qs_new_master=qs,
                               qs_corroboration=corr)


def test_s5_pass_on_expected_failover():
    result = classify_s5(s5_timeline(), corr={"NODE-C": True})
    assert result["verdict"] == h.PASS, result
    assert result["metrics"]["promotion_delay_s"] == 25
    assert result["metrics"]["expected_candidate"] == "NODE-C"


def test_s5_without_promotion_is_fail():
    post = [sample(t, {"NODE-A": None, "NODE-B": "FOLLOWER", "NODE-C": "FOLLOWER"},
                   hub_roles={"NODE-B": "FOLLOWER", "NODE-C": "FOLLOWER"}, down=("NODE-A",))
            for t in range(91)]
    assert "no_promotion_within_deadline" in classify_s5(post)["reasons"]


def test_s5_wrong_candidate_is_fail():
    post = s5_timeline()
    for s in post:
        if s["t"] >= 25:
            s["nodes"]["NODE-B"]["role"] = "MASTER"
            s["nodes"]["NODE-C"]["role"] = "FOLLOWER"
            s["hub"]["roles"].update({"NODE-B": "MASTER", "NODE-C": "FOLLOWER"})
    result = classify_s5(post)
    assert result["verdict"] == h.FAIL
    assert {"non_candidate_promoted", "no_promotion_within_deadline"} <= set(result["reasons"])


def test_s5_single_sample_second_master_is_fail():
    # A transient dual MASTER (one sample) is an improper promotion: FAIL.
    result = classify_s5(s5_timeline(extra_master=(26,)))
    assert result["verdict"] == h.FAIL
    assert {"non_candidate_promoted", "multiple_masters_observed"} <= set(result["reasons"])


def test_s5_non_candidate_before_candidate_is_fail():
    result = classify_s5(s5_timeline(extra_master=(20,)))
    assert "non_candidate_promoted" in result["reasons"]


def test_s5_premature_promotion_is_fail():
    assert "premature_promotion" in classify_s5(s5_timeline(promote_at=3))["reasons"]


def test_s5_master_not_stopped_is_fail():
    assert "master_not_stopped" in classify_s5(s5_timeline(), kill_info={"exit_code": None})["reasons"]


def test_s5_failed_master_still_serving_is_fail():
    post = s5_timeline()
    post[10]["nodes"]["NODE-A"] = {"ok": True, "role": "MASTER", "node_id": "NODE-A"}
    assert "failed_master_still_serving" in classify_s5(post)["reasons"]


def test_s5_hub_not_reaped_is_fail():
    assert "hub_failed_master_not_reaped" in classify_s5(s5_timeline(reap_at=10**6))["reasons"]


def test_s5_short_hold_is_fail():
    assert "not_converged" in classify_s5(s5_timeline(end=40))["reasons"]


def test_s5_qs_and_state_write_outcomes():
    assert "distributed_sync_accepted_with_n3" in classify_s5(s5_timeline(), qs="ACCEPTED")["reasons"]
    assert "state_written_with_n3" in classify_s5(s5_timeline(), logs={"event_persisted": 1})["reasons"]
    blocked = classify_s5(s5_timeline(), corr={"NODE-C": False})
    assert blocked["verdict"] == h.BLOCKED


def test_s5_empty_is_blocked():
    assert classify_s5([])["verdict"] == h.BLOCKED


def test_claims_do_not_assert_consensus():
    assert "not claimed" in h.CLAIMS["distributed_consensus"]
    assert "not claimed" in h.CLAIMS["master_fencing"]
    assert "not tested" in h.CLAIMS["replication"]
    assert set(h.CLAIMS) >= {"liveness_detection", "leader_election"}


# ======================================================================
# 3. orchestrator with stand-in processes (not the Nexus runtime)
# ======================================================================

STUB_HUB = r'''
import json, os, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
port = urlparse(os.environ["NEXUS_HUB_URL"]).port
nodes = json.loads(os.environ["STUB_NODES"])
reap = float(os.environ.get("STUB_REAP_S", "1.0"))
peers = {}
def poll():
    while True:
        for nid, web in nodes.items():
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{web}/status", timeout=0.3) as r:
                    d = json.loads(r.read())
                peers[nid] = {"role": d["role"], "ip": "127.0.0.1", "seen": time.time()}
            except Exception:
                pass
        now = time.time()
        for k in [k for k, v in list(peers.items()) if now - v["seen"] > reap]:
            peers.pop(k, None)
        time.sleep(0.1)
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        body = json.dumps({k: {"role": v["role"], "ip": v["ip"]} for k, v in list(peers.items())}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
threading.Thread(target=poll, daemon=True).start()
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''

STUB_CORE = r'''
import json, logging, os, socket, struct, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stub")
node_id, web, tcp, role = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
mode = json.loads(os.environ.get("STUB_MODE", "{}")).get(node_id, "normal")
if mode == "exit_now":
    sys.exit(7)
state = {"role": role}
if mode == "leak_secret":
    log.info("debug secret=%s", os.environ["NEXUS_SECRET_KEY"])
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        ident = "IMPOSTOR" if mode == "wrong_identity" else node_id
        body = json.dumps({"node_id": ident, "role": state["role"], "height": 0}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
srv = HTTPServer(("127.0.0.1", web), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
def tcp_server():
    s = socket.socket()
    s.bind(("127.0.0.1", tcp))
    s.listen(5)
    while True:
        c, _ = s.accept()
        try:
            size = struct.unpack("!I", c.recv(4))[0]
            c.recv(size)
            if mode == "accept_sync":
                p = json.dumps({"type": "SYNC_BATCH", "blocks": []}).encode()
                c.sendall(struct.pack("!I", len(p)) + p)
            else:
                log.warning("distributed_sync_blocked node=%s operation=state_summary "
                            "reason=quorum_commit_not_implemented", node_id)
        finally:
            c.close()
threading.Thread(target=tcp_server, daemon=True).start()
if mode == "thread_crash":
    def boom():
        raise RuntimeError("stub thread crash")
    threading.Thread(target=boom).start()
log.info("core_ready node=%s role=%s", node_id, role)
master_web = int(os.environ.get("STUB_MASTER_WEB", "0"))
candidates = json.loads(os.environ.get("STUB_CANDIDATES", "[]"))
detect = float(os.environ.get("STUB_DETECT_S", "1.0"))
started = last_ok = time.time()
while True:
    time.sleep(0.1)
    if mode == "promote_early" and state["role"] == "FOLLOWER" and time.time() - started > 0.8:
        state["role"] = "MASTER"
        log.info("leadership_promoted node=%s role=MASTER", node_id)
    if state["role"] != "FOLLOWER" or not master_web:
        continue
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{master_web}/status", timeout=0.2).close()
        last_ok = time.time()
    except Exception:
        if time.time() - last_ok > detect:
            log.warning("master_missing node=%s seconds=%.1f", node_id, time.time() - last_ok)
            if node_id in candidates:
                state["role"] = "MASTER"
                log.info("leadership_promoted node=%s role=MASTER", node_id)
            else:
                last_ok = time.time()
'''

FAST = dict(sample_interval_s=0.2, http_timeout_s=0.5, hub_ready_timeout_s=10.0,
            readiness_timeout_s=10.0, settle_s=0.4, s1_window_s=2.0, s5_baseline_s=1.0,
            s5_promotion_deadline_s=8.0, s5_hold_s=1.5, s5_min_observation_s=2.0,
            min_promotion_delay_s=0.5, max_observation_gap_s=1.5, min_availability=0.9,
            terminate_grace_s=2.0)


@pytest.fixture
def stub_env(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "nexus_rendezvous.py").write_text(STUB_HUB, encoding="utf-8")
    (root / "nexus_distributed_core.py").write_text(STUB_CORE, encoding="utf-8")
    ports = [_free_port() for _ in range(7)]
    nodes = (
        h.NodeSpec("NODE-A", "127.0.0.1", ports[1], ports[2], "MASTER", True),
        h.NodeSpec("NODE-B", "127.0.0.1", ports[3], ports[4], "FOLLOWER", True),
        h.NodeSpec("NODE-C", "127.0.0.1", ports[5], ports[6], "FOLLOWER", True),
    )
    cfg = h.HarnessConfig(runtime_root=root, cluster_size=3,
                          hub=h.HubSpec("127.0.0.1", ports[0], True),
                          nodes=nodes, timing=h.Timing(**FAST))
    monkeypatch.setenv("STUB_NODES", json.dumps({n.node_id: n.web_port for n in nodes}))
    monkeypatch.setenv("STUB_MASTER_WEB", str(nodes[0].web_port))
    monkeypatch.setenv("STUB_CANDIDATES", json.dumps(["NODE-C"]))
    monkeypatch.setenv("STUB_MODE", "{}")
    return cfg, tmp_path


def make_run(cfg, tmp_path, scenario):
    run = h.Run(cfg, scenario, tmp_path / "evidence", SECRET)
    run.work_dir = tmp_path / f"work-{run.run_id}"
    run.evidence_dir.mkdir(parents=True)
    return run


def execute(run):
    code = run.execute_after_preflight(run.base_evidence())
    evidence_text = (run.evidence_dir / "evidence.json").read_text(encoding="utf-8")
    return code, json.loads(evidence_text), evidence_text


def assert_all_children_stopped(run, evidence):
    assert run.procs, "run started no processes"
    for name, proc in run.procs.items():
        assert proc.popen.poll() is not None, f"{name} still running"
    assert evidence["shutdown"]["all_stopped"] is True
    assert evidence["shutdown"]["completed_monotonic_s"] <= evidence["evidence_written_monotonic_s"]


def assert_no_secret(run):
    for path in run.evidence_dir.rglob("*"):
        if path.is_file():
            assert SECRET not in path.read_text(encoding="utf-8", errors="replace"), path


def test_orchestrator_s1_pass_with_stubs(stub_env):
    cfg, tmp = stub_env
    run = make_run(cfg, tmp, "s1")
    code, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.PASS, ev["result"]
    assert code == 0
    assert_all_children_stopped(run, ev)
    assert_no_secret(run)
    assert ev["result"]["metrics"]["qs_c01_log_corroboration"] == {n: True for n in IDS}
    assert set(p.name for p in (run.evidence_dir / "logs").iterdir()) == {
        "hub.log", "NODE-A.log", "NODE-B.log", "NODE-C.log"}
    assert (run.evidence_dir / "SHA256SUMS").is_file()
    assert ev["claims"] == h.CLAIMS
    # databases and logs live in the isolated work dir, one per node
    assert all((run.work_dir / n).is_dir() for n in IDS)


def test_orchestrator_evidence_has_no_local_identity(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setattr(h.socket, "gethostname", lambda: FAKE_HOST)
    monkeypatch.setattr(h.tempfile, "gettempdir", lambda: str(tmp))
    run = make_run(cfg, tmp, "s1")  # work dir is tmp/work-<run_id>: "under temp"
    _, ev, _ = execute(run)
    assert_all_children_stopped(run, ev)
    assert ev["host"]["hostname"] == h.REDACTED_HOSTNAME
    assert ev["work_dir"] == h.REDACTED_TEMP + os.sep + run.work_dir.name
    temp = str(tmp)
    forbidden = {FAKE_HOST.lower(), temp.lower(), json.dumps(temp)[1:-1].lower()}
    for path in run.evidence_dir.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for item in forbidden:
                assert item not in text, (path.name, item)


def test_orchestrator_s1_early_promotion_is_fail(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-C": "promote_early"}))
    run = make_run(cfg, tmp, "s1")
    code, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.FAIL and code == 1
    assert {"follower_promoted_while_master_alive", "multiple_masters_observed"} <= set(
        ev["result"]["reasons"])
    assert_all_children_stopped(run, ev)


def test_orchestrator_s1_accepted_sync_is_fail(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-B": "accept_sync"}))
    run = make_run(cfg, tmp, "s1")
    _, ev, _ = execute(run)
    assert "distributed_sync_accepted_with_n3" in ev["result"]["reasons"]
    assert ev["result"]["verdict"] == h.FAIL


def test_orchestrator_s5_pass_with_stubs(stub_env):
    cfg, tmp = stub_env
    run = make_run(cfg, tmp, "s5")
    code, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.PASS, ev["result"]
    assert code == 0
    fo = ev["result"]["metrics"]["failover"]
    assert fo["expected_candidate"] == "NODE-C" and fo["multi_master_samples"] == 0
    assert fo["detection_delay_s"] is not None
    assert_all_children_stopped(run, ev)


def test_orchestrator_s5_two_promotions_is_fail(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_CANDIDATES", json.dumps(["NODE-B", "NODE-C"]))
    run = make_run(cfg, tmp, "s5")
    _, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.FAIL
    assert {"non_candidate_promoted", "multiple_masters_observed"} <= set(ev["result"]["reasons"])
    assert_all_children_stopped(run, ev)


def test_startup_failure_is_blocked_and_cleans_up(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-B": "exit_now"}))
    run = make_run(cfg, tmp, "s1")
    code, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.BLOCKED and code == 3
    assert ev["result"]["reasons"] == ["local_process_exited_early"]
    assert ev["result"]["metrics"]["detail"]["process"] == "NODE-B"
    assert_all_children_stopped(run, ev)


def test_child_thread_death_is_blocked(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-C": "thread_crash"}))
    run = make_run(cfg, tmp, "s1")
    _, ev, _ = execute(run)
    assert ev["result"]["reasons"] == ["local_child_thread_died"]
    assert_all_children_stopped(run, ev)


def test_wrong_identity_never_becomes_ready(stub_env, monkeypatch):
    cfg, tmp = stub_env
    cfg.timing.readiness_timeout_s = 2.0
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-B": "wrong_identity"}))
    run = make_run(cfg, tmp, "s1")
    _, ev, _ = execute(run)
    assert ev["result"]["reasons"] == ["readiness_timeout"]
    assert_all_children_stopped(run, ev)


def test_port_taken_before_start_is_blocked_and_foreign_listener_survives(stub_env):
    cfg, tmp = stub_env
    foreign = socket.socket()
    foreign.bind(("127.0.0.1", cfg.node("NODE-B").web_port))
    foreign.listen(1)
    try:
        run = make_run(cfg, tmp, "s1")
        _, ev, _ = execute(run)
        assert ev["result"]["reasons"] == ["port_taken_before_start"]
        assert_all_children_stopped(run, ev)
        # the pre-existing listener was not touched: still open, still bound
        assert foreign.fileno() != -1
        assert foreign.getsockname()[1] == cfg.node("NODE-B").web_port
        assert h.port_in_use(cfg.node("NODE-B").web_port)
    finally:
        foreign.close()


def test_preexisting_process_is_never_stopped(stub_env, monkeypatch):
    cfg, tmp = stub_env
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-B": "exit_now"}))
        run = make_run(cfg, tmp, "s1")
        execute(run)
        assert sleeper.poll() is None
        assert sleeper.pid not in {p.popen.pid for p in run.procs.values()}
    finally:
        sleeper.terminate()
        sleeper.wait(10)


@pytest.mark.parametrize("exc, reason", [
    (RuntimeError(f"boom {SECRET}"), "harness_error"),
    (KeyboardInterrupt(), "interrupted"),
    (h.HarnessInterrupted("SIGTERM"), "interrupted"),
])
def test_exceptions_are_blocked_cleanup_and_no_secret(stub_env, monkeypatch, exc, reason):
    cfg, tmp = stub_env

    def explode(self):
        raise exc
    monkeypatch.setattr(h.Run, "run_s1", explode)
    run = make_run(cfg, tmp, "s1")
    code, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.BLOCKED and code == 3
    assert ev["result"]["reasons"] == [reason]
    assert_all_children_stopped(run, ev)
    assert_no_secret(run)


def test_secret_printed_by_child_is_redacted(stub_env, monkeypatch):
    cfg, tmp = stub_env
    monkeypatch.setenv("STUB_MODE", json.dumps({"NODE-A": "leak_secret"}))
    run = make_run(cfg, tmp, "s1")
    _, ev, _ = execute(run)
    assert ev["result"]["verdict"] == h.PASS, ev["result"]
    assert "[REDACTED]" in (run.evidence_dir / "logs" / "NODE-A.log").read_text(encoding="utf-8")
    assert_no_secret(run)


def test_execute_runs_preflight_and_starts_nothing_when_blocked(stub_env):
    cfg, tmp = stub_env
    run = h.Run(cfg, "s1", tmp / "evidence", "")   # no secret, no exposure ack
    run.work_dir = tmp / "work-blocked"
    assert run.execute() == 3
    ev = json.loads((run.evidence_dir / "evidence.json").read_text(encoding="utf-8"))
    assert "preflight:secret" in ev["result"]["reasons"]
    # the stub runtime has no wildcard binds, so exposure itself passes here;
    # the real runtime case is covered by test_exposure_audit_finds_runtime_wildcard_binds
    assert ev["preflight"]["checks"]["exposure"]["wildcard_binds"] == []
    assert run.procs == {} and not run.work_dir.exists()


def test_orphan_guard_kills_children_when_harness_dies(tmp_path):
    beat = tmp_path / "beat.txt"
    launcher = tmp_path / "launcher.py"
    launcher.write_text(
        "import importlib.util, subprocess, sys, time\n"
        f"spec = importlib.util.spec_from_file_location('h', r'{HERE / 's1s5_harness.py'}')\n"
        "h = importlib.util.module_from_spec(spec); sys.modules['h'] = h\n"
        "spec.loader.exec_module(h)\n"
        "g = h.OrphanGuard()\n"
        "child = [sys.executable, '-c', 'import time,sys\\nwhile True:\\n "
        "open(sys.argv[1],\"w\").write(str(time.time())); time.sleep(0.1)', sys.argv[1]]\n"
        "p = h.start_process('beat', child, h.Path(sys.argv[2]), dict(h.os.environ), "
        "h.Path(sys.argv[2]) / 'beat.log', g)\n"
        "print(g.mode, p.orphan_protected, flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    parent = subprocess.Popen([sys.executable, "-B", str(launcher), str(beat), str(tmp_path)],
                              stdout=subprocess.PIPE, text=True)
    line = parent.stdout.readline().split()
    deadline = time.time() + 10
    while not beat.exists() and time.time() < deadline:
        time.sleep(0.1)
    assert beat.exists()
    assert line[1] == "True", line
    parent.kill()            # hard kill: no finally/cleanup runs in the launcher
    parent.wait(10)
    parent.stdout.close()
    time.sleep(1.0)
    first = beat.read_text()
    time.sleep(1.0)
    assert beat.read_text() == first, "child kept running after its harness died"


# ======================================================================
# non-destructive guarantees (static)
# ======================================================================

def test_harness_source_has_no_destructive_operations():
    source = (HERE / "s1s5_harness.py").read_text(encoding="utf-8")
    for forbidden in ("rmtree", "os.remove(", ".unlink(", "os.rmdir", "git reset",
                      "git clean", "git checkout", "git push", "git commit",
                      "netsh", "New-NetFirewallRule", "w32tm", "taskkill", "os.kill(",
                      "killpg", "TerminateProcess", "psutil"):
        assert forbidden not in source, forbidden


def test_child_env_passes_secret_only_through_environment():
    cfg = h.parse_config(base_config())
    cmd = h.node_command(cfg, cfg.node("NODE-A"))
    assert not any(SECRET in part or "secret" in part.lower() for part in cmd)
    env = h.child_env(cfg, SECRET, Path("db"))
    assert env["NEXUS_SECRET_KEY"] == SECRET
    assert env["NEXUS_CLUSTER_SIZE"] == "3"
    assert "-B" in cmd and env["PYTHONDONTWRITEBYTECODE"] == "1"
