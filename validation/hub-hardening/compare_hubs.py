"""W07 comparison runner: original vs experimental hub, loopback only.

Writes one JSON evidence file to ./evidence/. The test secret is generated per
run and never written. Exit: 0 all experimental checks PASS, 1 any FAIL.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hub_probes as hp  # noqa: E402

REPO_ROOT = HERE.parents[1]
RUNTIME_FILES = ["nexus_rendezvous.py", "nexus_distributed_core.py", "nexus_protocol.py",
                 "nexus_transport.py", "web_panel.py"]
CLUSTER_MIN_FREE_MB = 2048


def free_memory_mb() -> float | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return round(status.ullAvailPhys / 1048576, 1)
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True,
                          text=True, check=False).stdout.strip()


def listening(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def check(rows, name, item, experimental_ok, original_obs, measured, note=""):
    rows.append({
        "check": name, "mission_item": item,
        "verdict": "PASS" if experimental_ok else "FAIL",
        "original": original_obs, "measurements": measured, "note": note,
    })


def run() -> int:
    secret = hp.new_test_secret()
    started = time.time()
    hub_8500_before = listening(8500)
    threads_before = threading.active_count()
    rows: list[dict] = []

    def both(fn, *args, limits=None):
        out = {}
        for kind in ("original", "experimental"):
            extra = {"limits": limits} if (limits and kind == "experimental") else {}
            target = hp.make_target(kind, secret, **extra)
            try:
                out[kind] = fn(target, *args)
            finally:
                out[kind + "_stop"] = target.stop()
        return out

    r = both(hp.probe_idle_client, 2.5)
    check(rows, "idle_client_does_not_block", 12,
          r["experimental"]["concurrent_peers_request"].get("status") == 200
          and r["experimental"]["idle_connection"]["closed"],
          "LIMITATION_REPRODUCED" if r["original"]["concurrent_peers_request"].get("error") == "timeout" else "NOT_REPRODUCED",
          r)
    r = both(hp.probe_partial_headers, 2.5)
    check(rows, "partial_headers_time_out", 11,
          r["experimental"]["concurrent_peers_request"].get("status") == 200
          and r["experimental"]["partial_connection"]["closed"],
          "LIMITATION_REPRODUCED" if r["original"]["concurrent_peers_request"].get("error") == "timeout" else "NOT_REPRODUCED",
          r)
    r = both(hp.probe_partial_body, secret, 2.5)
    check(rows, "partial_body_times_out", 11,
          r["experimental"]["partial_connection"]["closed"] and not r["experimental"]["peer_registered"]
          and r["experimental"]["concurrent_peers_request"].get("status") == 200,
          "LIMITATION_REPRODUCED" if r["original"]["concurrent_peers_request"].get("error") == "timeout" else "NOT_REPRODUCED",
          r)
    r = both(hp.probe_slow_drip, 4.0)
    check(rows, "slow_drip_cut_by_deadline", 14,
          not r["experimental"]["survived_full_window"],
          "LIMITATION_REPRODUCED" if r["original"]["survived_full_window"] else "NOT_REPRODUCED",
          r, f"request_deadline_s={hp.TEST_LIMITS.request_deadline_s} (test limits)")
    r = both(hp.probe_concurrent, secret, 20)
    check(rows, "concurrent_requests", 13,
          r["experimental"]["register_200"] == 20 and r["experimental"]["peers_200"] == 20,
          "OK" if r["original"]["register_200"] == 20 else "DEGRADED", r)
    r = both(hp.probe_parallel_replay, secret, 16)
    check(rows, "parallel_replay_once", 18, r["experimental"]["accepted"] == 1,
          "OK" if r["original"]["accepted"] == 1 else "BROKEN", r)
    r = both(hp.probe_capacity, 4, limits=hp.CAPACITY_LIMITS)
    exp = r["experimental"]
    check(rows, "capacity_limit_and_recovery", 16,
          exp["overflow_503"] == 4 and exp["peers_during_saturation"] == 503 and exp["peers_after_release"] == 200,
          "LIMITATION_REPRODUCED" if r["original"]["peers_during_saturation"] == "timeout" else "NOT_REPRODUCED",
          r, "original has no admission control; while saturated it does not answer")
    r = both(hp.probe_shutdown_pending, 1.5)
    check(rows, "shutdown_with_pending_clients", 15,
          r["experimental"]["shutdown_completed_with_client_open"] and not r["experimental"]["threads_alive"],
          "LIMITATION_REPRODUCED" if not r["original"]["shutdown_completed_with_client_open"] else "NOT_REPRODUCED",
          r)
    r = both(hp.probe_unhandled_exception)
    check(rows, "handler_exception_contained", 17,
          r["experimental"]["while_corrupt"] == 500 and r["experimental"]["after_repair"] == 200,
          "LIMITATION_REPRODUCED" if r["original"]["while_corrupt"] == "RemoteDisconnected" else "NOT_REPRODUCED",
          r, "original prints a traceback to stderr and drops the connection")
    r = both(hp.probe_port_sharing)
    check(rows, "exclusive_port_bind", 25, not r["experimental"]["second_bind_allowed"],
          "LIMITATION_REPRODUCED" if r["original"]["second_bind_allowed"] else "NOT_REPRODUCED",
          r, "Windows-specific: SO_REUSEADDR lets another socket bind a listening port")
    r = both(hp.oversized_header)
    check(rows, "oversized_headers_rejected", 29,
          r["experimental"] == {"header_line_70k": 431, "headers_150": 431},
          "OK" if r["original"] == {"header_line_70k": 431, "headers_150": 431} else "DIFFERENT", r)
    r = both(hp.probe_node_client, secret)
    check(rows, "runtime_node_client_compatible", 19,
          r["experimental"] == r["original"] and r["experimental"]["a_register"] and r["experimental"]["peers_ok"],
          "OK", r, "uses NexusDistributedCore.post_envelope/build_*_envelope unchanged")
    r = both(hp.probe_node_client_unavailable, secret, "blocked")
    check(rows, "node_client_when_hub_blocked", 20,
          r["experimental"]["register_ok"] and r["experimental"]["elapsed_s"] < 0.5,
          "LIMITATION_REPRODUCED" if not r["original"]["register_ok"] else "NOT_REPRODUCED", r)

    a = {x["case"]: x for x in both(hp.auth_matrix, secret)["original"]}
    b_target = hp.make_target("experimental", secret)
    try:
        b = {x["case"]: x for x in hp.auth_matrix(b_target, secret)}
    finally:
        b_target.stop()
    diffs = sorted(c for c in a if (a[c]["status"], a[c]["body"] if c != "get_peers" else None)
                   != (b[c]["status"], b[c]["body"] if c != "get_peers" else None))
    check(rows, "auth_and_contract_parity", "18/19/27/28", diffs == ["get_unknown_path"],
          "BASELINE", {"cases": len(a), "differences": diffs,
                       "statuses": {c: [a[c]["status"], b[c]["status"]] for c in a}},
          "only deliberate difference: unknown GET path gets 404 instead of no response")

    rows.append({"check": "s1_s5_cluster_with_experimental_hub", "mission_item": "38",
                 "verdict": "BLOCKED", "original": "n/a",
                 "measurements": {"free_memory_mb": free_memory_mb(), "required_mb": CLUSTER_MIN_FREE_MB},
                 "note": "multiprocess cluster run not executed: memory gate and no integration authorization"})

    threads_after = threading.active_count()
    verdicts = [row["verdict"] for row in rows]
    evidence = {
        "mission": "W07", "kind": "hub-comparison", "run_id": uuid.uuid4().hex[:8],
        "started_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "python": platform.python_version(),
                 "free_memory_mb": free_memory_mb()},
        "git": {"branch": git("rev-parse", "--abbrev-ref", "HEAD"), "commit": git("rev-parse", "HEAD"),
                "runtime_blobs": {f: git("hash-object", f) for f in RUNTIME_FILES},
                "runtime_modified": git("status", "--porcelain", "--", *RUNTIME_FILES)},
        "artifacts_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(HERE.glob("*.py"))},
        "network": {"bind": "127.0.0.1 only, ephemeral ports",
                    "port_8500_listening_before": hub_8500_before,
                    "port_8500_listening_after": listening(8500)},
        "test_limits": hp.experimental_hub.limits_dict(hp.TEST_LIMITS),
        "threads": {"before": threads_before, "after": threads_after},
        "summary": {v: verdicts.count(v) for v in ("PASS", "FAIL", "BLOCKED")},
        "claims": {"distributed_consensus": "not claimed", "master_fencing": "not claimed",
                   "scope": "hub HTTP availability/robustness only"},
        "checks": rows,
    }
    text = json.dumps(evidence, indent=2, ensure_ascii=False, default=str)
    assert secret not in text, "secret leaked into evidence"
    out_dir = HERE / "evidence"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"hub-compare-{stamp}-{evidence['run_id']}.json"
    path.write_text(text, encoding="utf-8")
    for row in rows:
        print(f"{row['verdict']:8} {row['check']:40} original={row['original']}")
    print("summary", evidence["summary"], "evidence", path.name)
    return 1 if "FAIL" in verdicts else 0


if __name__ == "__main__":
    raise SystemExit(run())
