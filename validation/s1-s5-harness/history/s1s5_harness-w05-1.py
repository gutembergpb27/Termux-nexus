#!/usr/bin/env python3
"""Nexus V2700 - S1/S5 harness (W05).

S1: the MASTER stays MASTER while it is alive (no follower promotion).
S5: the MASTER is lost; followers detect it and one survivor is promoted.

The harness drives the unmodified runtime (nexus_rendezvous.py and
nexus_distributed_core.py) as real child processes. Nothing in the
runtime is mocked or patched. Every run uses a fresh work directory for
databases and logs and a fresh evidence directory. The harness never
deletes files and only stops processes that it started itself.

Stdlib only, so the same file runs on Windows and in Termux.

Exit codes: 0 PASS, 1 FAIL, 2 usage/config error, 3 BLOCKED.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import platform
import re
import secrets as _secrets
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HARNESS_VERSION = "w05-1"

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
EXIT_CODES = {PASS: 0, FAIL: 1, BLOCKED: 3}
EXIT_CONFIG_ERROR = 2

# Memory gate established for integration tests (W04-I6 mp_gate
# MIN_FREE_MB = 2048). The harness refuses any lower value: lowering it
# needs an explicit authorization, which is not a command-line flag.
MIN_FREE_MB_FLOOR = 2048
RAM_BUDGET_MB = 2048          # max combined RSS of local child processes
MEMORY_PRESSURE_FLOOR_MB = 512  # abort if free memory drops below this

# Runtime facts read from the code at commit 30b774da (not configurable
# there, so the harness checks them instead of assuming otherwise).
EXPECTED_CLUSTER_SIZE = 3
HUB_PORT = 8500                 # nexus_rendezvous.py binds 0.0.0.0:8500
LIVENESS_THRESHOLD_S = 15.0     # follower promotes after delta > 15 s
POLL_INTERVAL_S = 5.0           # async_polling_loop sleep
HUB_PEER_TIMEOUT_S = 30.0       # nexus_rendezvous.PEER_TIMEOUT

MIN_SECRET_LENGTH = 16
MAX_ABS_NTP_OFFSET_S = 1.0      # per host, so two hosts differ by <= 2 s
NTP_SERVERS = ("a.st1.ntp.br", "pool.ntp.org", "time.google.com")

RUNTIME_FILES = (
    "nexus_distributed_core.py",
    "nexus_rendezvous.py",
    "nexus_protocol.py",
    "nexus_transport.py",
    "web_panel.py",
    "persistence.py",
)

LOG_EVENTS = (
    "core_ready",
    "polling_started",
    "master_missing",
    "leadership_promotion_deferred",
    "leadership_promotion_blocked_no_quorum",
    "leadership_promotion_started",
    "leadership_promoted",
    "peer_sync_failed",
    "peer_sync_completed",
    "sync_batch_applied",
    "distributed_sync_blocked",
    "distributed_write_blocked",
    "event_persisted",
    "tcp_protocol_error",
    "tcp_error",
    "tcp_message_unsupported",
    "polling_error",
    "hub_request_failed",
    "peer_fetch_failed",
)
_LOG_EVENT_RE = re.compile(r"\b(" + "|".join(LOG_EVENTS) + r")\b")
_LOG_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) ")

HARNESS_DIR = Path(__file__).resolve().parent
DEFAULT_RUNTIME_ROOT = HARNESS_DIR.parent.parent
DEFAULT_EVIDENCE_ROOT = HARNESS_DIR / "evidence"


class ConfigError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    host: str
    web_port: int
    tcp_port: int
    initial_role: str
    local: bool


@dataclass(frozen=True)
class HubSpec:
    host: str
    port: int
    local: bool

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class Timing:
    sample_interval_s: float = 1.0
    http_timeout_s: float = 2.0
    hub_ready_timeout_s: float = 20.0
    readiness_timeout_s: float = 90.0
    settle_s: float = 12.0
    s1_window_s: float = 120.0
    s5_baseline_s: float = 20.0
    s5_promotion_deadline_s: float = 90.0
    s5_hold_s: float = 30.0
    min_promotion_delay_s: float = LIVENESS_THRESHOLD_S - POLL_INTERVAL_S
    concurrent_master_grace_s: float = 2 * POLL_INTERVAL_S
    max_observation_gap_s: float = 10.0
    min_availability: float = 0.95
    terminate_grace_s: float = 5.0


@dataclass
class HarnessConfig:
    runtime_root: Path
    cluster_size: int
    hub: HubSpec
    nodes: tuple[NodeSpec, ...]
    timing: Timing
    min_free_mb: int = MIN_FREE_MB_FLOOR
    expected_core_git_blob: str | None = None

    @property
    def node_ids(self) -> list[str]:
        return [n.node_id for n in self.nodes]

    def node(self, node_id: str) -> NodeSpec:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise ConfigError(f"unknown node_id {node_id!r}")

    @property
    def initial_master(self) -> str:
        return next(n.node_id for n in self.nodes if n.initial_role == "MASTER")

    @property
    def single_host(self) -> bool:
        return self.hub.local and all(n.local for n in self.nodes)

    def public_dict(self) -> dict[str, Any]:
        """Config as recorded in evidence. Contains no secret."""
        return {
            "runtime_root": str(self.runtime_root),
            "cluster_size": self.cluster_size,
            "hub": asdict(self.hub),
            "nodes": [asdict(n) for n in self.nodes],
            "timing": asdict(self.timing),
            "min_free_mb": self.min_free_mb,
            "expected_core_git_blob": self.expected_core_git_blob,
        }


def _is_loopback(host: str) -> bool:
    return host in {"localhost", "::1"} or host.startswith("127.")


def _port(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{what} must be an integer")
    if not 1 <= value <= 65535:
        raise ConfigError(f"{what} out of range")
    return value


def parse_config(data: dict[str, Any], *, base_dir: Path | None = None) -> HarnessConfig:
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")

    root_value = data.get("runtime_root")
    if root_value:
        root = Path(root_value)
        if not root.is_absolute() and base_dir is not None:
            root = (base_dir / root).resolve()
    else:
        root = DEFAULT_RUNTIME_ROOT

    size = data.get("cluster_size", EXPECTED_CLUSTER_SIZE)
    if size != EXPECTED_CLUSTER_SIZE or isinstance(size, bool):
        raise ConfigError(
            f"cluster_size must be {EXPECTED_CLUSTER_SIZE} for S1/S5 (got {size!r})"
        )

    hub_raw = data.get("hub")
    if not isinstance(hub_raw, dict):
        raise ConfigError("hub section is required")
    hub = HubSpec(
        host=str(hub_raw.get("host", "")).strip(),
        port=_port(hub_raw.get("port", HUB_PORT), "hub.port"),
        local=bool(hub_raw.get("local", False)),
    )
    if not hub.host:
        raise ConfigError("hub.host is required")
    if "<" in hub.host or ">" in hub.host:
        raise ConfigError("hub.host is a placeholder; set the current address")
    if hub.port != HUB_PORT:
        raise ConfigError(f"hub.port must be {HUB_PORT}: the runtime hub port is fixed")

    nodes_raw = data.get("nodes")
    if not isinstance(nodes_raw, list) or len(nodes_raw) != EXPECTED_CLUSTER_SIZE:
        raise ConfigError(f"exactly {EXPECTED_CLUSTER_SIZE} nodes are required")

    nodes = []
    for i, raw in enumerate(nodes_raw):
        if not isinstance(raw, dict):
            raise ConfigError(f"nodes[{i}] must be an object")
        role = str(raw.get("initial_role", "")).upper()
        if role not in {"MASTER", "FOLLOWER"}:
            raise ConfigError(f"nodes[{i}].initial_role must be MASTER or FOLLOWER")
        node = NodeSpec(
            node_id=str(raw.get("node_id", "")).strip(),
            host=str(raw.get("host", "")).strip(),
            web_port=_port(raw.get("web_port"), f"nodes[{i}].web_port"),
            tcp_port=_port(raw.get("tcp_port"), f"nodes[{i}].tcp_port"),
            initial_role=role,
            local=bool(raw.get("local", False)),
        )
        if not node.node_id or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", node.node_id):
            raise ConfigError(f"nodes[{i}].node_id is invalid")
        if not node.host:
            raise ConfigError(f"nodes[{i}].host is required")
        if "<" in node.host or ">" in node.host:
            raise ConfigError(f"nodes[{i}].host is a placeholder; set the current address")
        nodes.append(node)

    ids = [n.node_id for n in nodes]
    if len(set(ids)) != len(ids):
        raise ConfigError("node_id values must be unique")
    if sum(n.initial_role == "MASTER" for n in nodes) != 1:
        raise ConfigError("exactly one node must start as MASTER")

    endpoints: dict[tuple[str, int], str] = {}
    if hub.local:
        endpoints[("local", hub.port)] = "hub"
    for n in nodes:
        for port, kind in ((n.web_port, "web"), (n.tcp_port, "tcp")):
            key = ("local" if n.local else n.host, port)
            if key in endpoints:
                raise ConfigError(f"port {port} used twice on host {key[0]}")
            endpoints[key] = f"{n.node_id}.{kind}"

    any_remote = (not hub.local) or any(not n.local for n in nodes)
    if any_remote:
        # The hub advertises each node by the source IP of its connection.
        # A local node that reaches the hub through loopback would be
        # advertised as 127.0.0.1 and be unreachable from the other host.
        if _is_loopback(hub.host):
            raise ConfigError(
                "hub.host is loopback but the topology has remote members; "
                "use the hub's LAN address"
            )
        for n in nodes:
            if _is_loopback(n.host):
                raise ConfigError(
                    f"{n.node_id}.host is loopback in a multi-host topology"
                )

    timing = Timing()
    for key, value in (data.get("timing") or {}).items():
        if not hasattr(timing, key):
            raise ConfigError(f"unknown timing key {key!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ConfigError(f"timing.{key} must be a positive number")
        setattr(timing, key, float(value))
    if timing.s1_window_s < 3 * LIVENESS_THRESHOLD_S:
        raise ConfigError(
            f"timing.s1_window_s must be >= {3 * LIVENESS_THRESHOLD_S:.0f} s "
            "(three liveness thresholds)"
        )
    if timing.min_availability > 1:
        raise ConfigError("timing.min_availability must be <= 1")
    if timing.s5_promotion_deadline_s <= LIVENESS_THRESHOLD_S:
        raise ConfigError("timing.s5_promotion_deadline_s must exceed the liveness threshold")

    min_free = data.get("min_free_mb", MIN_FREE_MB_FLOOR)
    if isinstance(min_free, bool) or not isinstance(min_free, int):
        raise ConfigError("min_free_mb must be an integer")
    if min_free < MIN_FREE_MB_FLOOR:
        raise ConfigError(
            f"min_free_mb below {MIN_FREE_MB_FLOOR} requires explicit authorization "
            "and is not accepted by this harness"
        )

    if "expected_core_sha256" in data:
        raise ConfigError(
            "expected_core_sha256 is not portable (CRLF checkout on Windows); "
            "use expected_core_git_blob"
        )
    sha = data.get("expected_core_git_blob")
    if sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", str(sha)):
        raise ConfigError("expected_core_git_blob must be 40 hex characters")

    return HarnessConfig(
        runtime_root=root,
        cluster_size=size,
        hub=hub,
        nodes=tuple(nodes),
        timing=timing,
        min_free_mb=min_free,
        expected_core_git_blob=sha.lower() if sha else None,
    )


def load_config(path: str | Path) -> HarnessConfig:
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return parse_config(data, base_dir=path.resolve().parent)


# ---------------------------------------------------------------------------
# Host measurements (memory, ports, clock, runtime integrity)
# ---------------------------------------------------------------------------


def available_memory_mb() -> float | None:
    if os.name == "nt":
        class _MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullAvailPhys / (1024 * 1024)
        return None
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def process_rss_mb(pid: int) -> float | None:
    if os.name == "nt":
        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.K32GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
        ]
        handle = kernel32.OpenProcess(0x1000, 0, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            counters = _Counters()
            counters.cb = ctypes.sizeof(counters)
            if kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024 * 1024)
            return None
        finally:
            kernel32.CloseHandle(handle)
    try:
        with open(f"/proc/{pid}/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def memory_gate(available_mb: float | None, min_free_mb: int) -> dict[str, Any]:
    if available_mb is None:
        return {"status": BLOCKED, "reason": "memory_unmeasurable", "min_free_mb": min_free_mb}
    ok = available_mb >= min_free_mb
    return {
        "status": PASS if ok else BLOCKED,
        "reason": None if ok else "insufficient_free_memory",
        "available_mb": round(available_mb, 1),
        "min_free_mb": min_free_mb,
    }


def port_in_use(port: int) -> bool:
    """Non-invasive check: connect to loopback, then try a bind without listen."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return True
    return False


def sntp_offset(host: str, timeout: float = 3.0) -> tuple[float, float]:
    """Return (server_minus_local_s, rtt_ms) from one SNTP exchange."""
    packet = b"\x1b" + 47 * b"\0"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        t1 = time.time()
        sock.sendto(packet, (host, 123))
        data, _ = sock.recvfrom(48)
        t4 = time.time()
    if len(data) < 48:
        raise ValueError("short SNTP reply")
    seconds, fraction = struct.unpack("!II", data[40:48])
    server = seconds - 2208988800 + fraction / 2**32
    return server - (t1 + t4) / 2, (t4 - t1) * 1000


def clock_check(single_host: bool, servers: tuple[str, ...] = NTP_SERVERS) -> dict[str, Any]:
    results = []
    for host in servers:
        try:
            offset, rtt = sntp_offset(host)
            results.append({"server": host, "offset_s": round(offset, 4), "rtt_ms": round(rtt, 1)})
        except (OSError, ValueError) as exc:
            results.append({"server": host, "error": type(exc).__name__})
    offsets = [r["offset_s"] for r in results if "offset_s" in r]
    median = statistics.median(offsets) if offsets else None
    if single_host:
        status, reason = PASS, "single_host_clock_skew_not_applicable"
    elif median is None:
        status, reason = BLOCKED, "clock_unverifiable_no_ntp_reply"
    elif abs(median) > MAX_ABS_NTP_OFFSET_S:
        status, reason = BLOCKED, "clock_offset_exceeds_limit"
    else:
        status, reason = PASS, None
    return {
        "status": status,
        "reason": reason,
        "ntp_minus_local_median_s": median,
        "max_abs_offset_s": MAX_ABS_NTP_OFFSET_S,
        "samples": results,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_id(path: Path) -> str:
    """Git blob id of a text file after CRLF->LF normalization.

    Equals `git hash-object` for the committed (LF) content on both a
    Windows CRLF checkout and an LF checkout in Termux; git not required.
    """
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def runtime_integrity(cfg: HarnessConfig) -> dict[str, Any]:
    root = cfg.runtime_root
    files = {}
    missing = []
    for name in RUNTIME_FILES:
        path = root / name
        if path.is_file():
            files[name] = sha256_file(path)
        else:
            missing.append(name)
    commit = _git(root, "rev-parse", "HEAD")
    modified = _git(root, "status", "--porcelain", "--", *RUNTIME_FILES)
    reasons = []
    if missing:
        reasons.append("runtime_files_missing")
    if modified:
        reasons.append("runtime_files_modified")
    core = files.get("nexus_distributed_core.py")
    blobs = {name: git_blob_id(root / name) for name in files}
    if cfg.expected_core_git_blob and blobs.get("nexus_distributed_core.py") != cfg.expected_core_git_blob:
        reasons.append("core_git_blob_mismatch")
    return {
        "status": BLOCKED if reasons else PASS,
        "reasons": reasons,
        "runtime_root": str(root),
        "git_commit": commit,
        "git_modified_runtime_files": modified.splitlines() if modified else [],
        "git_blob": blobs,
        "sha256_raw_bytes": files,
        "sha256_note": "raw bytes differ between CRLF (Windows) and LF checkouts; identity is the git blob",
        "missing": missing,
    }


def secret_gate(secret: str | None) -> dict[str, Any]:
    """Never returns or records the secret itself, its hash or its length."""
    value = (secret or "").strip()
    if not value:
        return {"status": BLOCKED, "reason": "NEXUS_SECRET_KEY_missing"}
    if len(value) < MIN_SECRET_LENGTH:
        return {"status": BLOCKED, "reason": "NEXUS_SECRET_KEY_too_short"}
    return {"status": PASS, "reason": None, "present": True}


def preflight(cfg: HarnessConfig, scope_node_ids: list[str], *, include_hub: bool,
              secret: str | None, available_mb: float | None = None,
              check_clock: bool = True) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["secret"] = secret_gate(secret)
    if available_mb is None:
        available_mb = available_memory_mb()
    checks["memory"] = memory_gate(available_mb, cfg.min_free_mb)
    checks["runtime"] = runtime_integrity(cfg)

    busy = []
    ports = [cfg.hub.port] if include_hub else []
    for node_id in scope_node_ids:
        n = cfg.node(node_id)
        ports += [n.web_port, n.tcp_port]
    for port in ports:
        if port_in_use(port):
            busy.append(port)
    checks["ports"] = {
        "status": BLOCKED if busy else PASS,
        "checked": ports,
        "in_use": busy,
    }
    checks["clock"] = (
        clock_check(cfg.single_host) if check_clock
        else {"status": PASS, "reason": "skipped_by_caller"}
    )
    blocked = sorted(k for k, v in checks.items() if v["status"] != PASS)
    return {"status": BLOCKED if blocked else PASS, "blocked_checks": blocked, "checks": checks}


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


def http_get_json(url: str, timeout: float) -> tuple[int | None, Any, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(1024 * 1024)
            return resp.status, json.loads(body.decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTPError:{exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return None, None, f"{type(exc).__name__}:{type(reason).__name__}"


def observe_node(node: NodeSpec, timeout: float) -> dict[str, Any]:
    status, body, error = http_get_json(f"http://{node.host}:{node.web_port}/status", timeout)
    if status == 200 and isinstance(body, dict):
        return {
            "ok": True,
            "role": str(body.get("role", "")).upper() or None,
            "node_id": body.get("node_id"),
            "height": body.get("height"),
        }
    return {"ok": False, "error": error or f"status:{status}"}


def observe_hub(hub: HubSpec, timeout: float) -> dict[str, Any]:
    status, body, error = http_get_json(f"{hub.url}/peers", timeout)
    if status == 200 and isinstance(body, dict):
        return {
            "ok": True,
            "roles": {
                str(k): str(v.get("role", "")).upper()
                for k, v in body.items() if isinstance(v, dict)
            },
            "ips": {str(k): v.get("ip") for k, v in body.items() if isinstance(v, dict)},
        }
    return {"ok": False, "error": error or f"status:{status}"}


def take_sample(cfg: HarnessConfig, t: float) -> dict[str, Any]:
    timeout = cfg.timing.http_timeout_s
    return {
        "t": round(t, 3),
        "utc": utc_now(),
        "nodes": {n.node_id: observe_node(n, timeout) for n in cfg.nodes},
        "hub": observe_hub(cfg.hub, timeout),
    }


def _frame(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("closed")
        data += chunk
    return data


def qs_c01_probe(host: str, tcp_port: int, timeout: float = 3.0) -> str:
    """Ask a node to serve blocks (STATE_SUMMARY, read-only on the node).

    With NEXUS_CLUSTER_SIZE=3 the runtime must refuse and close the
    connection without a SYNC_BATCH. SYNC_BATCH is never sent because it
    could write state if a node wrongly accepted it.
    """
    try:
        conn = socket.create_connection((host, tcp_port), timeout=timeout)
    except OSError:
        return "UNREACHABLE"
    try:
        conn.settimeout(timeout)
        conn.sendall(_frame({"type": "STATE_SUMMARY", "payload": {"height": 0}}))
        header = _recv_exact(conn, 4)
        size = struct.unpack("!I", header)[0]
        if not 0 < size <= 16 * 1024 * 1024:
            return "UNEXPECTED_RESPONSE"
        message = json.loads(_recv_exact(conn, size).decode("utf-8"))
        if isinstance(message, dict) and message.get("type") == "SYNC_BATCH":
            return "ACCEPTED"
        return "UNEXPECTED_RESPONSE"
    except (ConnectionError, ConnectionResetError):
        return "REFUSED_CLOSED"
    except socket.timeout:
        return "NO_RESPONSE_TIMEOUT"
    except (OSError, ValueError):
        return "REFUSED_CLOSED"
    finally:
        conn.close()


def parse_log_events(text: str, node_id: str) -> list[dict[str, Any]]:
    events = []
    for line in text.splitlines():
        match = _LOG_EVENT_RE.search(line)
        if not match:
            continue
        epoch = None
        tm = _LOG_TIME_RE.match(line)
        if tm:
            try:
                base = time.mktime(time.strptime(tm.group(1), "%Y-%m-%d %H:%M:%S"))
                epoch = base + int(tm.group(2)) / 1000
            except (ValueError, OverflowError):
                epoch = None
        events.append({"node": node_id, "event": match.group(1), "epoch": epoch, "line": line[:300]})
    return events


def count_events(events: list[dict[str, Any]], *, after: float | None = None,
                 before: float | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in events:
        epoch = ev.get("epoch")
        if after is not None and (epoch is None or epoch < after):
            continue
        if before is not None and (epoch is None or epoch >= before):
            continue
        counts[ev["event"]] = counts.get(ev["event"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Classification (pure functions over recorded observations)
# ---------------------------------------------------------------------------


def expected_candidate(node_ids: list[str], failed_master: str) -> str:
    """Runtime rule: promotion goes to max(eligible FOLLOWER ids incl. self)."""
    survivors = [n for n in node_ids if n != failed_master]
    return max(survivors)


def _availability(samples: list[dict[str, Any]], node_id: str, start: float,
                  end: float) -> tuple[float, float]:
    ok_times = [s["t"] for s in samples if s["nodes"].get(node_id, {}).get("ok")]
    if not samples:
        return 0.0, end - start
    ratio = len(ok_times) / len(samples)
    if not ok_times:
        return ratio, end - start
    points = [start] + ok_times + [end]
    gap = max(b - a for a, b in zip(points, points[1:]))
    return ratio, gap


def _identity_errors(samples: list[dict[str, Any]]) -> list[str]:
    bad = set()
    for s in samples:
        for node_id, obs in s["nodes"].items():
            if obs.get("ok") and obs.get("node_id") not in (None, node_id):
                bad.add(node_id)
    return sorted(bad)


def _verdict(reasons: list[str]) -> str:
    return FAIL if reasons else PASS


def classify_stable_master(samples: list[dict[str, Any]], node_ids: list[str],
                           master: str, timing: Timing, *, start: float,
                           end: float, log_counts: dict[str, int],
                           qs_results: dict[str, str] | None = None,
                           label: str = "s1") -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {"samples": len(samples), "window_s": round(end - start, 3)}

    if not samples:
        return {"verdict": FAIL, "reasons": [f"{label}_no_observations"],
                "warnings": warnings, "metrics": metrics}

    if _identity_errors(samples):
        reasons.append("identity_mismatch")

    unexpected_masters = set()
    master_lost = False
    for s in samples:
        for node_id, obs in s["nodes"].items():
            if not obs.get("ok"):
                continue
            role = obs.get("role")
            if node_id != master and role == "MASTER":
                unexpected_masters.add(node_id)
            if node_id == master and role != "MASTER":
                master_lost = True
    if unexpected_masters:
        reasons.append("follower_promoted_while_master_alive")
        metrics["unexpected_masters"] = sorted(unexpected_masters)
    if master_lost:
        reasons.append("master_role_lost")

    hub_div = 0
    for s in samples:
        hub = s.get("hub", {})
        if not hub.get("ok"):
            continue
        roles = hub.get("roles", {})
        expected = {n: ("MASTER" if n == master else "FOLLOWER") for n in node_ids}
        if {n: roles.get(n) for n in node_ids} != expected:
            hub_div += 1
    if hub_div:
        reasons.append("hub_role_divergence")
        metrics["hub_divergent_samples"] = hub_div

    for event in ("leadership_promotion_started", "leadership_promoted"):
        if log_counts.get(event):
            reasons.append(f"log_{event}")
    if log_counts.get("master_missing"):
        reasons.append("log_master_missing")
    if log_counts.get("peer_sync_failed"):
        warnings.append(f"liveness_probe_failures={log_counts['peer_sync_failed']}")
    for event in ("sync_batch_applied", "peer_sync_completed", "event_persisted"):
        if log_counts.get(event):
            reasons.append(f"log_{event}_with_n3")

    availability = {}
    for node_id in node_ids:
        ratio, gap = _availability(samples, node_id, start, end)
        availability[node_id] = {"ratio": round(ratio, 4), "max_gap_s": round(gap, 3)}
        if ratio < timing.min_availability or gap > timing.max_observation_gap_s:
            if "observability_gap" not in reasons:
                reasons.append("observability_gap")
    metrics["availability"] = availability

    if qs_results is not None:
        metrics["qs_c01_probe"] = qs_results
        if any(v == "ACCEPTED" for v in qs_results.values()):
            reasons.append("distributed_sync_accepted_with_n3")
        elif any(v != "REFUSED_CLOSED" for v in qs_results.values()):
            reasons.append("qs_c01_probe_inconclusive")

    return {"verdict": _verdict(reasons), "reasons": reasons,
            "warnings": warnings, "metrics": metrics}


def _longest_run(samples: list[dict[str, Any]], predicate) -> float:
    longest = 0.0
    run_start = None
    for s in samples:
        if predicate(s):
            if run_start is None:
                run_start = s["t"]
            longest = max(longest, s["t"] - run_start)
        else:
            run_start = None
    return longest


def classify_failover(post: list[dict[str, Any]], node_ids: list[str],
                      failed_master: str, timing: Timing, *, t_kill: float,
                      kill_info: dict[str, Any], log_events_after_kill: dict[str, int],
                      detection_delay_s: float | None = None,
                      qs_new_master: str | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    candidate = expected_candidate(node_ids, failed_master)
    survivors = [n for n in node_ids if n != failed_master]
    metrics: dict[str, Any] = {
        "expected_candidate": candidate,
        "survivors": survivors,
        "samples": len(post),
        "detection_delay_s": detection_delay_s,
    }

    if kill_info.get("exit_code") is None:
        reasons.append("master_not_stopped")

    if _identity_errors(post):
        reasons.append("identity_mismatch")

    revived = [s["t"] for s in post
               if s["t"] >= t_kill + 2 and s["nodes"].get(failed_master, {}).get("ok")]
    if revived:
        reasons.append("failed_master_still_serving")

    def masters(s):
        return sorted(n for n in survivors
                      if s["nodes"].get(n, {}).get("ok")
                      and s["nodes"][n].get("role") == "MASTER")

    first = next((s for s in post if masters(s)), None)
    if first is None:
        reasons.append("no_promotion_within_deadline")
        return {"verdict": FAIL, "reasons": reasons, "warnings": warnings, "metrics": metrics}

    t_promote = first["t"]
    metrics["promoted"] = masters(first)
    metrics["promotion_delay_s"] = round(t_promote - t_kill, 3)
    if candidate not in masters(first):
        reasons.append("unexpected_candidate")
    if t_promote - t_kill < timing.min_promotion_delay_s:
        reasons.append("premature_promotion")
    if t_promote - t_kill > timing.s5_promotion_deadline_s:
        reasons.append("no_promotion_within_deadline")

    after = [s for s in post if s["t"] >= t_promote]
    concurrent = _longest_run(after, lambda s: len(masters(s)) >= 2)
    concurrent_any = any(len(masters(s)) >= 2 for s in after)
    metrics["concurrent_master_max_s"] = round(concurrent, 3)
    if concurrent > timing.concurrent_master_grace_s:
        reasons.append("persistent_concurrent_master")
    elif concurrent_any:
        warnings.append("transient_concurrent_master")

    def final_ok(s):
        for n in survivors:
            obs = s["nodes"].get(n, {})
            if not obs.get("ok"):
                continue
            want = "MASTER" if n == candidate else "FOLLOWER"
            if obs.get("role") != want:
                return False
        return True

    t_conv = None
    for i, s in enumerate(after):
        if all(final_ok(x) for x in after[i:]):
            t_conv = s["t"]
            break
    end = post[-1]["t"]
    if t_conv is None or end - t_conv < timing.s5_hold_s:
        reasons.append("not_converged")
    else:
        metrics["convergence_delay_s"] = round(t_conv - t_kill, 3)
        metrics["stable_hold_s"] = round(end - t_conv, 3)
        hold = [s for s in after if s["t"] >= t_conv]
        for n in survivors:
            ratio, gap = _availability(hold, n, t_conv, end)
            if ratio < timing.min_availability or gap > timing.max_observation_gap_s:
                reasons.append("observability_gap")
                break

    hub_samples = [s["hub"] for s in post if s.get("hub", {}).get("ok")]
    if not hub_samples:
        reasons.append("hub_unobservable")
    else:
        last = hub_samples[-1]["roles"]
        want = {n: ("MASTER" if n == candidate else "FOLLOWER") for n in survivors}
        if {n: last.get(n) for n in survivors} != want:
            reasons.append("hub_not_converged")
        if failed_master in last:
            reasons.append("hub_failed_master_not_reaped")

    if log_events_after_kill.get("sync_batch_applied") or log_events_after_kill.get("event_persisted"):
        reasons.append("state_written_with_n3")
    metrics["log_events_after_kill"] = log_events_after_kill

    if qs_new_master is not None:
        metrics["qs_c01_probe_new_master"] = qs_new_master
        if qs_new_master == "ACCEPTED":
            reasons.append("distributed_sync_accepted_with_n3")
        elif qs_new_master != "REFUSED_CLOSED":
            reasons.append("qs_c01_probe_inconclusive")

    return {"verdict": _verdict(sorted(set(reasons), key=reasons.index)),
            "reasons": sorted(set(reasons), key=reasons.index),
            "warnings": warnings, "metrics": metrics}


# ---------------------------------------------------------------------------
# Process management (only processes started here)
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class Managed:
    name: str
    popen: subprocess.Popen
    log_path: Path
    started_utc: str
    stopped: dict[str, Any] = field(default_factory=dict)


def child_env(cfg: HarnessConfig, secret: str, db_path: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    env["NEXUS_SECRET_KEY"] = secret          # passed by environment, never argv
    env["NEXUS_CLUSTER_SIZE"] = str(cfg.cluster_size)
    env["NEXUS_HUB_URL"] = cfg.hub.url
    env["PYTHONUNBUFFERED"] = "1"
    if db_path is not None:
        env["NEXUS_DB_PATH"] = str(db_path)
    return env


def start_process(name: str, cmd: list[str], cwd: Path, env: dict[str, str],
                  log_path: Path) -> Managed:
    log = open(log_path, "wb")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        popen = subprocess.Popen(
            cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        )
    finally:
        log.close()
    return Managed(name=name, popen=popen, log_path=log_path, started_utc=utc_now())


def stop_process(proc: Managed, grace_s: float) -> dict[str, Any]:
    if proc.stopped:
        return proc.stopped
    method = "already_exited"
    if proc.popen.poll() is None:
        method = "terminate"
        proc.popen.terminate()
        try:
            proc.popen.wait(timeout=grace_s)
        except subprocess.TimeoutExpired:
            method = "kill"
            proc.popen.kill()
            try:
                proc.popen.wait(timeout=5)
            except subprocess.TimeoutExpired:
                method = "kill_unconfirmed"
    proc.stopped = {"method": method, "exit_code": proc.popen.poll(), "utc": utc_now()}
    return proc.stopped


def node_command(cfg: HarnessConfig, node: NodeSpec) -> list[str]:
    return [sys.executable, "-u", "-B", str(cfg.runtime_root / "nexus_distributed_core.py"),
            node.node_id, str(node.web_port), str(node.tcp_port), node.initial_role]


def hub_command(cfg: HarnessConfig) -> list[str]:
    return [sys.executable, "-u", "-B", str(cfg.runtime_root / "nexus_rendezvous.py")]


def scrub(text: str, secret: str | None) -> str:
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return text


# ---------------------------------------------------------------------------
# Run orchestration
# ---------------------------------------------------------------------------


class Abort(Exception):
    def __init__(self, verdict: str, reason: str, detail: Any = None):
        super().__init__(reason)
        self.verdict = verdict
        self.reason = reason
        self.detail = detail


class Run:
    def __init__(self, cfg: HarnessConfig, scenario: str, evidence_root: Path,
                 secret: str):
        self.cfg = cfg
        self.scenario = scenario
        self.secret = secret
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"{scenario}-{stamp}-{_secrets.token_hex(3)}"
        self.evidence_dir = Path(evidence_root) / self.run_id
        self.work_dir = Path(tempfile.gettempdir()) / f"nexus-s1s5-{self.run_id}"
        self.procs: dict[str, Managed] = {}
        self.samples: list[dict[str, Any]] = []
        self.marks: dict[str, Any] = {}
        self.memory: dict[str, Any] = {"peak_children_rss_mb": 0.0, "min_available_mb": None}
        self.t0 = time.monotonic()
        self.epoch0 = time.time()

    # -- helpers --------------------------------------------------------
    def now(self) -> float:
        return time.monotonic() - self.t0

    def mark(self, name: str, **extra: Any) -> float:
        t = self.now()
        self.marks[name] = {"t": round(t, 3), "epoch": time.time(), "utc": utc_now(), **extra}
        print(f"[{self.run_id}] t={t:7.1f}s {name} {extra if extra else ''}", flush=True)
        return t

    def check_resources(self) -> None:
        total = 0.0
        for p in self.procs.values():
            if p.popen.poll() is None:
                rss = process_rss_mb(p.popen.pid)
                total += rss or 0.0
        self.memory["peak_children_rss_mb"] = round(max(self.memory["peak_children_rss_mb"], total), 1)
        avail = available_memory_mb()
        if avail is not None:
            prev = self.memory["min_available_mb"]
            self.memory["min_available_mb"] = round(avail if prev is None else min(prev, avail), 1)
        if total > RAM_BUDGET_MB:
            raise Abort(BLOCKED, "ram_budget_exceeded", {"children_rss_mb": total})
        if avail is not None and avail < MEMORY_PRESSURE_FLOOR_MB:
            raise Abort(BLOCKED, "memory_pressure", {"available_mb": avail})

    def check_local_alive(self, allowed_dead: set[str] = frozenset()) -> None:
        for name, p in self.procs.items():
            if name in allowed_dead:
                continue
            if p.popen.poll() is not None:
                raise Abort(BLOCKED, "local_process_exited_early",
                            {"process": name, "exit_code": p.popen.returncode})

    def sample(self, allowed_dead: set[str] = frozenset()) -> dict[str, Any]:
        self.check_resources()
        self.check_local_alive(allowed_dead)
        s = take_sample(self.cfg, self.now())
        self.samples.append(s)
        return s

    def sleep_until(self, t_next: float) -> None:
        delay = t_next - self.now()
        if delay > 0:
            time.sleep(delay)

    def sample_for(self, duration: float, allowed_dead: set[str] = frozenset()) -> list[dict[str, Any]]:
        start = self.now()
        out = []
        while self.now() - start < duration:
            t_next = self.now() + self.cfg.timing.sample_interval_s
            out.append(self.sample(allowed_dead))
            self.sleep_until(t_next)
        return out

    # -- phases ---------------------------------------------------------
    def start_hub(self) -> None:
        if not self.cfg.hub.local:
            return
        hub_dir = self.work_dir / "hub"
        hub_dir.mkdir()
        self.procs["hub"] = start_process(
            "hub", hub_command(self.cfg), hub_dir,
            child_env(self.cfg, self.secret, None), hub_dir / "hub.log",
        )
        deadline = self.now() + self.cfg.timing.hub_ready_timeout_s
        while self.now() < deadline:
            self.check_local_alive()
            if observe_hub(self.cfg.hub, self.cfg.timing.http_timeout_s)["ok"]:
                self.mark("hub_ready")
                return
            time.sleep(0.5)
        raise Abort(BLOCKED, "hub_not_ready")

    def start_node(self, node: NodeSpec) -> None:
        node_dir = self.work_dir / node.node_id
        node_dir.mkdir()
        self.procs[node.node_id] = start_process(
            node.node_id, node_command(self.cfg, node), node_dir,
            child_env(self.cfg, self.secret, node_dir / "persistence" / f"nexus_{node.node_id}.db"),
            node_dir / f"{node.node_id}.log",
        )
        self.mark("node_started", node=node.node_id, pid=self.procs[node.node_id].popen.pid)

    def wait_master_registered(self) -> None:
        master = self.cfg.initial_master
        deadline = self.now() + self.cfg.timing.readiness_timeout_s
        while self.now() < deadline:
            self.check_local_alive()
            hub = observe_hub(self.cfg.hub, self.cfg.timing.http_timeout_s)
            if hub["ok"] and hub["roles"].get(master) == "MASTER":
                self.mark("master_registered", node=master)
                return
            time.sleep(0.5)
        raise Abort(BLOCKED, "master_not_registered")

    def ready(self, s: dict[str, Any]) -> bool:
        if not s["hub"].get("ok"):
            return False
        for n in self.cfg.nodes:
            obs = s["nodes"][n.node_id]
            if not obs.get("ok") or obs.get("role") != n.initial_role or obs.get("node_id") != n.node_id:
                return False
            if s["hub"]["roles"].get(n.node_id) != n.initial_role:
                return False
        return True

    def bring_up(self) -> None:
        self.work_dir.mkdir(parents=False, exist_ok=False)
        self.start_hub()
        master = self.cfg.node(self.cfg.initial_master)
        if master.local:
            self.start_node(master)
        self.wait_master_registered()
        for n in self.cfg.nodes:
            if n.local and n.node_id != master.node_id:
                self.start_node(n)
        remote = [n.node_id for n in self.cfg.nodes if not n.local]
        if remote:
            self.mark("waiting_remote_nodes", nodes=remote)
        deadline = self.now() + self.cfg.timing.readiness_timeout_s
        last = None
        while self.now() < deadline:
            last = self.sample()
            if self.ready(last):
                self.mark("cluster_ready")
                return
            time.sleep(self.cfg.timing.sample_interval_s)
        raise Abort(BLOCKED, "readiness_timeout", last)

    def qs_probe_all(self, node_ids: list[str]) -> dict[str, str]:
        return {n: qs_c01_probe(self.cfg.node(n).host, self.cfg.node(n).tcp_port)
                for n in node_ids}

    def collect_logs(self) -> list[dict[str, Any]]:
        events = []
        logs_dir = self.evidence_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        for name, p in self.procs.items():
            try:
                text = p.log_path.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                continue
            text = scrub(text, self.secret)
            (logs_dir / f"{name}.log").write_text(text, encoding="utf-8")
            if name != "hub":
                events += parse_log_events(text, name)
        return events

    # -- scenarios ------------------------------------------------------
    def run_s1(self) -> dict[str, Any]:
        t = self.cfg.timing
        self.sample_for(t.settle_s)
        start = self.mark("s1_window_start")
        window = self.sample_for(t.s1_window_s)
        end = self.mark("s1_window_end")
        qs = self.qs_probe_all(self.cfg.node_ids)
        self.marks["s1_window_end"]["qs_c01_probe"] = qs
        return {"window": window, "start": start, "end": end, "qs": qs}

    def run_s5(self) -> dict[str, Any]:
        t = self.cfg.timing
        master = self.cfg.initial_master
        if master not in self.procs:
            raise Abort(BLOCKED, "master_not_local_cannot_stop")
        self.sample_for(t.settle_s)
        b_start = self.mark("s5_baseline_start")
        baseline = self.sample_for(t.s5_baseline_s)
        b_end = self.mark("s5_baseline_end")
        qs = self.qs_probe_all(self.cfg.node_ids)
        t_kill = self.mark("master_stop_requested", node=master)
        kill_info = stop_process(self.procs[master], t.terminate_grace_s)
        self.mark("master_stopped", node=master, **kill_info)
        dead = {master}
        survivors = [n for n in self.cfg.node_ids if n != master]
        candidate = expected_candidate(self.cfg.node_ids, master)
        post: list[dict[str, Any]] = []
        t_conv = None
        while True:
            t_next = self.now() + t.sample_interval_s
            s = self.sample(dead)
            post.append(s)
            elapsed = s["t"] - t_kill
            good = all(
                (not s["nodes"][n].get("ok"))
                or s["nodes"][n].get("role") == ("MASTER" if n == candidate else "FOLLOWER")
                for n in survivors
            ) and s["nodes"][candidate].get("role") == "MASTER"
            t_conv = (t_conv if t_conv is not None else s["t"]) if good else None
            if t_conv is not None and s["t"] - t_conv >= t.s5_hold_s and elapsed >= HUB_PEER_TIMEOUT_S + 5:
                break
            if t_conv is None and elapsed > t.s5_promotion_deadline_s:
                break
            if elapsed > t.s5_promotion_deadline_s + t.s5_hold_s + HUB_PEER_TIMEOUT_S:
                break
            self.sleep_until(t_next)
        self.mark("s5_observation_end")
        promoted = [n for n in survivors if post[-1]["nodes"][n].get("role") == "MASTER"]
        qs_new = qs_c01_probe(self.cfg.node(promoted[0]).host, self.cfg.node(promoted[0]).tcp_port) if promoted else None
        return {"baseline": baseline, "b_start": b_start, "b_end": b_end, "qs": qs,
                "t_kill": t_kill, "kill_info": kill_info, "post": post, "qs_new": qs_new}

    # -- top level ------------------------------------------------------
    def execute(self) -> int:
        self.evidence_dir.mkdir(parents=True, exist_ok=False)
        evidence: dict[str, Any] = {
            "harness_version": HARNESS_VERSION,
            "run_id": self.run_id,
            "scenario": self.scenario,
            "started_utc": utc_now(),
            "host": {"platform": platform.platform(), "python": sys.version.split()[0],
                     "hostname": socket.gethostname()},
            "config": self.cfg.public_dict(),
            "work_dir": str(self.work_dir),
            "secret": "provided via NEXUS_SECRET_KEY environment variable; not recorded",
        }
        local_nodes = [n.node_id for n in self.cfg.nodes if n.local]
        pre = preflight(self.cfg, local_nodes, include_hub=self.cfg.hub.local, secret=self.secret)
        evidence["preflight"] = pre
        result: dict[str, Any]
        if pre["status"] != PASS:
            result = {"verdict": BLOCKED, "reasons": pre["blocked_checks"], "warnings": [], "metrics": {}}
            return self.finish(evidence, result, [])

        data: dict[str, Any] = {}
        aborted: dict[str, Any] | None = None
        try:
            self.bring_up()
            data = self.run_s1() if self.scenario == "s1" else self.run_s5()
        except Abort as exc:
            aborted = {"verdict": exc.verdict, "reasons": [exc.reason], "warnings": [],
                       "metrics": {"detail": exc.detail}}
        except KeyboardInterrupt:
            aborted = {"verdict": BLOCKED, "reasons": ["interrupted_by_operator"],
                       "warnings": [], "metrics": {}}
        finally:
            # Always stop our own children before evidence is written.
            self.shutdown(evidence)
        if aborted is not None:
            return self.finish(evidence, aborted, [])

        events = self.collect_logs()
        ids = self.cfg.node_ids
        master = self.cfg.initial_master
        if self.scenario == "s1":
            e0 = self.epoch0 + data["start"]
            e1 = self.epoch0 + data["end"]
            result = classify_stable_master(
                data["window"], ids, master, self.cfg.timing, start=data["start"],
                end=data["end"], log_counts=count_events(events, after=e0, before=e1),
                qs_results=data["qs"],
            )
        else:
            e_kill = self.epoch0 + data["t_kill"]
            baseline = classify_stable_master(
                data["baseline"], ids, master, self.cfg.timing, start=data["b_start"],
                end=data["b_end"],
                log_counts=count_events(events, after=self.epoch0 + data["b_start"], before=e_kill),
                qs_results=data["qs"], label="s5_baseline",
            )
            detect = [ev["epoch"] for ev in events
                      if ev["event"] == "master_missing" and ev["epoch"] and ev["epoch"] >= e_kill]
            failover = classify_failover(
                data["post"], ids, master, self.cfg.timing, t_kill=data["t_kill"],
                kill_info=data["kill_info"], log_events_after_kill=count_events(events, after=e_kill),
                detection_delay_s=round(min(detect) - e_kill, 3) if detect else None,
                qs_new_master=data["qs_new"],
            )
            reasons = [f"baseline:{r}" for r in baseline["reasons"]] + failover["reasons"]
            result = {
                "verdict": FAIL if reasons else PASS,
                "reasons": reasons,
                "warnings": baseline["warnings"] + failover["warnings"],
                "metrics": {"baseline": baseline["metrics"], "failover": failover["metrics"]},
            }
        return self.finish(evidence, result, events)

    def shutdown(self, evidence: dict[str, Any]) -> None:
        order = [n for n in self.procs if n != "hub"] + (["hub"] if "hub" in self.procs else [])
        stops = {name: stop_process(self.procs[name], self.cfg.timing.terminate_grace_s) for name in order}
        evidence["shutdown"] = {
            "processes": stops,
            "all_stopped": all(s["exit_code"] is not None for s in stops.values()),
        }

    def finish(self, evidence: dict[str, Any], result: dict[str, Any],
               events: list[dict[str, Any]]) -> int:
        if not events and self.procs:
            events = self.collect_logs()
        evidence["result"] = result
        evidence["marks"] = self.marks
        evidence["memory"] = self.memory
        evidence["log_events"] = events[:2000]
        evidence["finished_utc"] = utc_now()
        evidence["interpretation_boundary"] = (
            "S1/S5 observe liveness, election and recoordination of the V2700 runtime. "
            "They do not test replication or consensus: with N=3 replication is "
            "fail-closed (QS-C01) and no quorum-commit protocol exists."
        )
        write_text(self.evidence_dir / "samples.jsonl",
                   "".join(json.dumps(s, sort_keys=True) + "\n" for s in self.samples), self.secret)
        write_text(self.evidence_dir / "evidence.json",
                   json.dumps(evidence, indent=2, sort_keys=True, default=str), self.secret)
        write_sha256sums(self.evidence_dir)
        print(json.dumps({"run_id": self.run_id, "verdict": result["verdict"],
                          "reasons": result["reasons"], "evidence_dir": str(self.evidence_dir)},
                         indent=2))
        return EXIT_CODES[result["verdict"]]


def write_text(path: Path, text: str, secret: str | None) -> None:
    path.write_text(scrub(text, secret), encoding="utf-8")


def write_sha256sums(directory: Path) -> None:
    lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}\n")
    (directory / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Remote node mode (e.g. NODE-C in Termux)
# ---------------------------------------------------------------------------


def run_node(cfg: HarnessConfig, node_id: str, duration_s: float, evidence_root: Path,
             secret: str) -> int:
    node = cfg.node(node_id)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"node-{node_id}-{stamp}-{_secrets.token_hex(3)}"
    evidence_dir = Path(evidence_root) / run_id
    evidence_dir.mkdir(parents=True, exist_ok=False)
    work_dir = Path(tempfile.gettempdir()) / f"nexus-s1s5-{run_id}"
    evidence: dict[str, Any] = {
        "harness_version": HARNESS_VERSION, "run_id": run_id, "mode": "node",
        "node_id": node_id, "started_utc": utc_now(), "config": cfg.public_dict(),
        "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        "work_dir": str(work_dir),
    }
    pre = preflight(cfg, [node_id], include_hub=False, secret=secret,
                    check_clock=not cfg.single_host)
    evidence["preflight"] = pre
    if pre["status"] != PASS:
        evidence["result"] = {"verdict": BLOCKED, "reasons": pre["blocked_checks"]}
        write_text(evidence_dir / "evidence.json", json.dumps(evidence, indent=2, default=str), secret)
        write_sha256sums(evidence_dir)
        print(json.dumps(evidence["result"]))
        return EXIT_CODES[BLOCKED]

    work_dir.mkdir(exist_ok=False)
    proc = start_process(node_id, node_command(cfg, node), work_dir,
                         child_env(cfg, secret, work_dir / "persistence" / f"nexus_{node_id}.db"),
                         work_dir / f"{node_id}.log")
    transitions = []
    last_role = None
    peak = 0.0
    verdict, reasons = PASS, []
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < duration_s:
            if proc.popen.poll() is not None:
                verdict, reasons = FAIL, ["node_process_exited_early"]
                break
            peak = max(peak, process_rss_mb(proc.popen.pid) or 0.0)
            if peak > RAM_BUDGET_MB:
                verdict, reasons = BLOCKED, ["ram_budget_exceeded"]
                break
            obs = observe_node(NodeSpec(node.node_id, "127.0.0.1", node.web_port, node.tcp_port,
                                        node.initial_role, True), cfg.timing.http_timeout_s)
            role = obs.get("role") if obs.get("ok") else None
            if role != last_role:
                transitions.append({"t": round(time.monotonic() - t0, 3), "utc": utc_now(), "role": role})
                print(f"[{node_id}] role={role}", flush=True)
                last_role = role
            time.sleep(cfg.timing.sample_interval_s)
    except KeyboardInterrupt:
        reasons.append("stopped_by_operator")
    finally:
        evidence["shutdown"] = stop_process(proc, cfg.timing.terminate_grace_s)
    text = scrub(proc.log_path.read_bytes().decode("utf-8", errors="replace"), secret)
    (evidence_dir / f"{node_id}.log").write_text(text, encoding="utf-8")
    evidence["role_transitions"] = transitions
    evidence["log_events"] = parse_log_events(text, node_id)[:2000]
    evidence["peak_rss_mb"] = round(peak, 1)
    evidence["result"] = {"verdict": verdict, "reasons": reasons,
                          "note": "node mode records local evidence; the S1/S5 verdict comes from the controller"}
    evidence["finished_utc"] = utc_now()
    write_text(evidence_dir / "evidence.json", json.dumps(evidence, indent=2, default=str), secret)
    write_sha256sums(evidence_dir)
    print(json.dumps({"run_id": run_id, **evidence["result"], "evidence_dir": str(evidence_dir)}, indent=2))
    return EXIT_CODES[verdict]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def plan_text(cfg: HarnessConfig, config_path: str) -> str:
    here = Path(__file__).resolve()
    lines = [
        "# S1/S5 execution plan (no secret is printed; set NEXUS_SECRET_KEY in each shell)",
        f"# runtime_root: {cfg.runtime_root}",
        f"# hub: {cfg.hub.url} ({'local' if cfg.hub.local else 'remote'})",
    ]
    for n in cfg.nodes:
        lines.append(f"# {n.node_id}: {n.host} web={n.web_port} tcp={n.tcp_port} "
                     f"role={n.initial_role} {'local' if n.local else 'REMOTE'}")
    lines.append("")
    lines.append(f"python {here.name} preflight --config {config_path}")
    for scenario in ("s1", "s5"):
        lines.append(f"python {here.name} run --scenario {scenario} --config {config_path}")
    for n in cfg.nodes:
        if not n.local:
            lines.append(f"# on host {n.host}, after the controller prints waiting_remote_nodes:")
            lines.append(f"python {here.name} node --config {config_path} --node-id {n.node_id}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run", "node", "plan"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        if name in ("run", "node", "preflight"):
            p.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
        if name == "run":
            p.add_argument("--scenario", choices=("s1", "s5"), required=True)
        if name == "node":
            p.add_argument("--node-id", required=True)
            p.add_argument("--duration-s", type=float, default=900.0)
        if name == "preflight":
            p.add_argument("--node-id", default=None,
                           help="check only this node (remote host); default: all local members")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (OSError, ValueError, ConfigError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    secret = os.environ.get("NEXUS_SECRET_KEY", "").strip()

    if args.command == "plan":
        print(plan_text(cfg, args.config))
        return 0

    if args.command == "preflight":
        scope = [args.node_id] if args.node_id else [n.node_id for n in cfg.nodes if n.local]
        try:
            report = preflight(cfg, scope, include_hub=cfg.hub.local and not args.node_id,
                               secret=secret)
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        report = {"harness_version": HARNESS_VERSION, "utc": utc_now(),
                  "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
                  "scope": scope, "config": cfg.public_dict(), **report}
        root = Path(args.evidence_root)
        root.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = root / f"preflight-{stamp}-{_secrets.token_hex(3)}.json"
        text = json.dumps(report, indent=2, sort_keys=True, default=str)
        write_text(out, text, secret)
        print(scrub(text, secret))
        print(f"report: {out}", file=sys.stderr)
        return EXIT_CODES[report["status"]]

    if args.command == "node":
        try:
            return run_node(cfg, args.node_id, args.duration_s, Path(args.evidence_root), secret)
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR

    run = Run(cfg, args.scenario, Path(args.evidence_root), secret)
    return run.execute()


if __name__ == "__main__":
    sys.exit(main())
