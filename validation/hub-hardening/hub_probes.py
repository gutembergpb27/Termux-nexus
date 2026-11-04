"""Loopback probes shared by the W07 tests and the comparison runner.

Two targets expose the same interface (``port``, ``peers``, ``stop()``):

- ``OriginalHubTarget``: the ORIGINAL ``NexusRendezvousHandler`` served by the
  same ``HTTPServer`` class the hub uses, bound to 127.0.0.1 on an ephemeral
  port, in-process. The hub's ``__main__`` block (0.0.0.0:8500, reaper) is
  never executed. Module globals are patched for the target's lifetime and
  restored afterwards.
- ``ExperimentalHubTarget``: ``experimental_hub.HardenedHub`` on 127.0.0.1.

Every client socket a probe opens is registered on the target and closed in
``stop()``, so a blocked original server can always be released.
"""
from __future__ import annotations

import http.client
import json
import secrets
import socket
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
for entry in (str(REPO_ROOT), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experimental_hub  # noqa: E402
import nexus_rendezvous as original  # noqa: E402
from nexus_protocol import NexusProtocol, ReplayCache  # noqa: E402

LOOPBACK = "127.0.0.1"


def new_test_secret() -> str:
    """Throwaway per-run secret. Never the cluster secret, never persisted."""
    return "w07-test-" + secrets.token_hex(16)


# ----------------------------------------------------------------------
# Targets
# ----------------------------------------------------------------------

class _TargetBase:
    kind = "base"

    def __init__(self) -> None:
        self._clients: list[socket.socket] = []
        self._clients_lock = threading.Lock()

    def track(self, sock: socket.socket) -> socket.socket:
        with self._clients_lock:
            self._clients.append(sock)
        return sock

    def close_clients(self) -> None:
        with self._clients_lock:
            clients, self._clients = self._clients, []
        for sock in clients:
            try:
                sock.close()
            except OSError:
                pass

    def raw_connect(self, timeout: float = 2.0, source: str | None = None) -> socket.socket:
        sock = socket.create_connection((LOOPBACK, self.port), timeout=timeout,
                                        source_address=(source, 0) if source else None)
        return self.track(sock)


class OriginalHubTarget(_TargetBase):
    kind = "original"

    def __init__(self, secret: str) -> None:
        super().__init__()
        self._saved = (original.PROTOCOL, original.REPLAY_CACHE, original.PEERS)
        original.PROTOCOL = NexusProtocol(secret)
        original.REPLAY_CACHE = ReplayCache()
        original.PEERS = {}
        self.server = HTTPServer((LOOPBACK, 0), original.NexusRendezvousHandler)
        self.port = int(self.server.server_address[1])
        self._thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.05),
            name="original-hub-under-test",
            daemon=True,
        )
        self._thread.start()

    @property
    def peers(self) -> dict:
        return original.PEERS

    def shutdown_with_timeout(self, timeout: float) -> dict[str, Any]:
        """Call shutdown() without releasing client sockets first."""
        started = time.monotonic()
        stopper = threading.Thread(target=self.server.shutdown, daemon=True)
        stopper.start()
        stopper.join(timeout)
        return {"completed": not stopper.is_alive(),
                "elapsed_s": round(time.monotonic() - started, 3),
                "_stopper": stopper}

    def stop(self) -> dict[str, Any]:
        started = time.monotonic()
        self.close_clients()  # release a handler blocked on a stalled client
        result = self.shutdown_with_timeout(5.0)
        self.server.server_close()
        self._thread.join(2.0)
        original.PROTOCOL, original.REPLAY_CACHE, original.PEERS = self._saved
        return {"clean": result["completed"] and not self._thread.is_alive(),
                "duration_s": round(time.monotonic() - started, 3),
                "threads_alive": [self._thread.name] if self._thread.is_alive() else []}


class ExperimentalHubTarget(_TargetBase):
    kind = "experimental"

    def __init__(self, secret: str, limits: experimental_hub.HubLimits | None = None, **kwargs) -> None:
        super().__init__()
        self.hub = experimental_hub.HardenedHub(secret, host=LOOPBACK, port=0, limits=limits, **kwargs)
        self.port = self.hub.port
        self.hub.start()

    @property
    def peers(self) -> dict:
        return self.hub.peers

    def stop(self) -> dict[str, Any]:
        report = self.hub.close()  # with client sockets still open
        self.close_clients()
        return report


# Short limits so the suite stays fast; same code paths as the defaults.
TEST_LIMITS = experimental_hub.HubLimits(
    max_connections=8,
    socket_timeout_s=0.5,
    request_deadline_s=1.5,
    shutdown_grace_s=1.0,
    reap_interval_s=0.2,
)


# Capacity probe: holders must outlive the probe, so idle timeouts are longer.
CAPACITY_LIMITS = experimental_hub.HubLimits(
    max_connections=8,
    socket_timeout_s=3.0,
    request_deadline_s=4.0,
    shutdown_grace_s=1.0,
    reap_interval_s=0.2,
)


def make_target(kind: str, secret: str, **kwargs):
    if kind == "original":
        return OriginalHubTarget(secret)
    kwargs.setdefault("limits", TEST_LIMITS)
    return ExperimentalHubTarget(secret, **kwargs)


# ----------------------------------------------------------------------
# Envelopes (same shape the node builds)
# ----------------------------------------------------------------------

def registration(protocol: NexusProtocol, node_id: str, role: str = "FOLLOWER",
                 web_port: int = 8082, tcp_port: int = 9092, **overrides) -> dict:
    return protocol.create_envelope(
        sender=overrides.pop("sender", node_id),
        message_type=overrides.pop("message_type", "REGISTER"),
        payload=overrides.pop("payload", {
            "node_id": node_id,
            "role": role,
            "web_port": web_port,
            "tcp_port": tcp_port,
            "protocol_version": 1,
            "capabilities": {"handlers": ["echo"]},
        }),
        **overrides,
    )


def heartbeat(protocol: NexusProtocol, node_id: str, role: str = "FOLLOWER", **overrides) -> dict:
    return protocol.create_envelope(
        sender=node_id,
        message_type="HEARTBEAT",
        payload=overrides.pop("payload", {
            "role": role,
            "capabilities": {"handlers": ["echo"]},
            "load": {"active_tasks": 0, "queued_tasks": 0, "completed_tasks": 0,
                     "failed_tasks": 0, "average_duration_ms": 0.0},
        }),
        **overrides,
    )


# ----------------------------------------------------------------------
# Raw HTTP helpers
# ----------------------------------------------------------------------

def http_call(port: int, method: str, path: str, body: bytes | None = None,
              timeout: float = 3.0, headers: dict | None = None) -> dict[str, Any]:
    """Return {status, json|text, elapsed_s} or {error, elapsed_s}."""
    started = time.monotonic()
    conn = http.client.HTTPConnection(LOOPBACK, port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        raw = response.read()
        result: dict[str, Any] = {"status": response.status}
        try:
            result["json"] = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            result["text"] = raw[:200].decode("utf-8", "replace")
    except (TimeoutError, socket.timeout):
        result = {"error": "timeout"}
    except (ConnectionError, http.client.HTTPException, OSError) as exc:
        result = {"error": type(exc).__name__}
    finally:
        conn.close()
    result["elapsed_s"] = round(time.monotonic() - started, 3)
    return result


def post_json(port: int, path: str, envelope: Any, timeout: float = 3.0) -> dict[str, Any]:
    body = json.dumps(envelope).encode("utf-8")
    return http_call(port, "POST", path, body, timeout,
                     {"Content-Type": "application/json", "Content-Length": str(len(body))})


def get_peers(port: int, timeout: float = 3.0) -> dict[str, Any]:
    return http_call(port, "GET", "/peers", timeout=timeout)


def wait_closed_by_server(sock: socket.socket, limit_s: float) -> dict[str, Any]:
    """Wait until the server closes ``sock`` (EOF/reset) or ``limit_s`` passes."""
    started = time.monotonic()
    sock.settimeout(0.1)
    data = b""
    while time.monotonic() - started < limit_s:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        except OSError:
            return {"closed": True, "after_s": round(time.monotonic() - started, 3), "data": data[:120].decode("latin-1")}
        if not chunk:
            return {"closed": True, "after_s": round(time.monotonic() - started, 3), "data": data[:120].decode("latin-1")}
        data += chunk
    return {"closed": False, "after_s": round(time.monotonic() - started, 3), "data": data[:120].decode("latin-1")}


def read_response_then_close(sock: socket.socket, limit_s: float) -> dict[str, Any]:
    """Behave like a real client: read the server's answer (or EOF), then close."""
    started = time.monotonic()
    sock.settimeout(0.1)
    data = b""
    closed = False
    while time.monotonic() - started < limit_s:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        except OSError:
            closed = True
            break
        if not chunk:
            closed = True
            break
        data += chunk
        if b"\r\n\r\n" in data and data.rstrip().endswith(b"}"):
            closed = True
            break
    sock.close()
    return {"closed": closed, "after_s": round(time.monotonic() - started, 3),
            "data": data[:400].decode("latin-1")}


# ----------------------------------------------------------------------
# Probes (each returns plain JSON-able measurements)
# ----------------------------------------------------------------------

def _with_blocker(target, blocker_bytes: bytes, probe_timeout: float = 2.0) -> dict[str, Any]:
    blocker = target.raw_connect()
    if blocker_bytes:
        blocker.sendall(blocker_bytes)
    time.sleep(0.3)  # let the server pick the blocker up first
    concurrent = get_peers(target.port, timeout=probe_timeout)
    return {"concurrent_peers_request": concurrent, "blocker": blocker}


def probe_idle_client(target, observe_s: float = 3.0) -> dict[str, Any]:
    """Item 12: a client connects and sends nothing."""
    result = _with_blocker(target, b"")
    blocker = result.pop("blocker")
    result["idle_connection"] = wait_closed_by_server(blocker, observe_s)
    return result


def probe_partial_headers(target, observe_s: float = 3.0) -> dict[str, Any]:
    """Item 11: request line and a header, but no terminating blank line."""
    result = _with_blocker(target, b"GET /peers HTTP/1.1\r\nHost: hub\r\n")
    blocker = result.pop("blocker")
    result["partial_connection"] = wait_closed_by_server(blocker, observe_s)
    return result


def probe_partial_body(target, secret: str, observe_s: float = 3.0) -> dict[str, Any]:
    """Item 11: Content-Length larger than the bytes actually sent."""
    body = json.dumps(registration(NexusProtocol(secret), "NODE-P")).encode()
    head = (f"POST /register HTTP/1.1\r\nHost: hub\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n").encode()
    result = _with_blocker(target, head + body[: len(body) // 2])
    blocker = result.pop("blocker")
    result["partial_connection"] = wait_closed_by_server(blocker, observe_s)
    result["peer_registered"] = "NODE-P" in target.peers
    return result


def probe_slow_drip(target, duration_s: float = 4.0, interval_s: float = 0.2) -> dict[str, Any]:
    """Item 14: one header byte at a time, each gap shorter than the socket timeout."""
    sock = target.raw_connect()
    payload = b"GET /peers HTTP/1.1\r\nX-Drip: " + b"a" * 4000
    started = time.monotonic()
    sent = 0
    cut_after = None
    sock.settimeout(0.05)
    while time.monotonic() - started < duration_s and sent < len(payload):
        try:
            sock.send(payload[sent:sent + 1])
            sent += 1
        except OSError:
            cut_after = round(time.monotonic() - started, 3)
            break
        try:
            if sock.recv(1024) == b"":
                cut_after = round(time.monotonic() - started, 3)
                break
        except (TimeoutError, socket.timeout):
            pass
        except OSError:
            cut_after = round(time.monotonic() - started, 3)
            break
        time.sleep(interval_s)
    return {"bytes_sent": sent, "cut_by_server_after_s": cut_after,
            "survived_full_window": cut_after is None}


def probe_concurrent(target, secret: str, clients: int = 20) -> dict[str, Any]:
    """Item 13: parallel registrations and peer reads."""
    protocol = NexusProtocol(secret)
    envelopes = [registration(protocol, f"NODE-{i:02d}", web_port=8100 + i, tcp_port=9100 + i)
                 for i in range(clients)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=clients * 2) as pool:
        regs = list(pool.map(lambda env: post_json(target.port, "/register", env, timeout=5), envelopes))
        reads = list(pool.map(lambda _: get_peers(target.port, timeout=5), range(clients)))
    final = get_peers(target.port, timeout=5)
    return {
        "clients": clients,
        "register_200": sum(1 for r in regs if r.get("status") == 200),
        "peers_200": sum(1 for r in reads if r.get("status") == 200),
        "errors": sorted({r.get("error") or str(r.get("status")) for r in regs + reads
                          if r.get("status") != 200}),
        "final_peer_count": len(final.get("json") or {}),
        "elapsed_s": round(time.monotonic() - started, 3),
    }


def probe_parallel_replay(target, secret: str, copies: int = 16) -> dict[str, Any]:
    """Item 18: the same signed envelope sent concurrently must be accepted once."""
    envelope = registration(NexusProtocol(secret), "NODE-R")
    barrier = threading.Barrier(copies)

    def send(_):
        barrier.wait(5)
        return post_json(target.port, "/register", envelope, timeout=5)

    with ThreadPoolExecutor(max_workers=copies) as pool:
        results = list(pool.map(send, range(copies)))
    statuses = [r.get("status", r.get("error")) for r in results]
    return {"copies": copies, "accepted": statuses.count(200), "rejected_401": statuses.count(401),
            "other": sorted({str(s) for s in statuses if s not in (200, 401)})}


def probe_capacity(target, extra: int = 4, max_connections: int | None = None) -> dict[str, Any]:
    """Item 16: hold more idle connections than the slot limit."""
    limit = max_connections or (target.hub.limits.max_connections if target.kind == "experimental" else 8)
    holders, connect_failures = [], 0
    for _ in range(limit):
        try:
            holders.append(target.raw_connect(timeout=1.0))
        except OSError:
            connect_failures += 1
    time.sleep(0.3)
    started = time.monotonic()
    overflow = []
    for _ in range(extra):
        try:
            sock = target.raw_connect(timeout=1.0)
        except OSError:
            connect_failures += 1
            overflow.append({"closed": False, "after_s": None, "data": ""})
            continue
        overflow.append(read_response_then_close(sock, 1.0))
    peers_during = get_peers(target.port, timeout=1.5)
    for sock in holders:
        sock.close()
    time.sleep(0.3)
    peers_after = get_peers(target.port, timeout=2.0)
    return {
        "held": len(holders),
        "connect_failures": connect_failures,
        "overflow_closed_fast": sum(1 for o in overflow if o["closed"] and o["after_s"] < 1.0),
        "overflow_503": sum(1 for o in overflow if " 503 " in o["data"]),
        "peers_during_saturation": peers_during.get("status", peers_during.get("error")),
        "peers_after_release": peers_after.get("status", peers_after.get("error")),
        "elapsed_s": round(time.monotonic() - started, 3),
    }


def probe_shutdown_pending(target, hold_s: float = 2.0) -> dict[str, Any]:
    """Item 15: stop the server while an idle client is still connected."""
    target.raw_connect()
    time.sleep(0.3)
    if target.kind == "original":
        attempt = target.shutdown_with_timeout(hold_s)
        stopper = attempt.pop("_stopper")
        target.close_clients()
        stopper.join(3.0)
        target.server.server_close()
        return {"shutdown_completed_with_client_open": attempt["completed"],
                "waited_s": attempt["elapsed_s"],
                "completed_after_client_closed": not stopper.is_alive()}
    report = target.hub.close()
    return {"shutdown_completed_with_client_open": report["clean"],
            "waited_s": report["duration_s"], "forced_connections": report["forced_connections"],
            "threads_alive": report["threads_alive"]}


def probe_unhandled_exception(target) -> dict[str, Any]:
    """Item 17: a corrupted peer record makes /peers raise inside the handler."""
    target.peers["CORRUPT"] = ["not-a-dict"]
    broken = get_peers(target.port, timeout=2)
    target.peers.pop("CORRUPT", None)
    healthy = get_peers(target.port, timeout=2)
    return {"while_corrupt": broken.get("status", broken.get("error")),
            "while_corrupt_body": broken.get("json"),
            "after_repair": healthy.get("status", healthy.get("error"))}


def auth_matrix(target, secret: str) -> list[dict[str, Any]]:
    """Items 18/19: signed-contract cases; same inputs for both hubs."""
    good = NexusProtocol(secret)
    bad = NexusProtocol("w07-wrong-" + uuid.uuid4().hex)
    port = target.port
    cases: list[tuple[str, str, Any]] = []
    reg = registration(good, "NODE-A", role="MASTER", web_port=8081, tcp_port=9091)
    cases.append(("register_valid", "/register", reg))
    cases.append(("register_replay", "/register", reg))
    cases.append(("heartbeat_valid", "/heartbeat", heartbeat(good, "NODE-A", role="MASTER")))
    tampered = registration(good, "NODE-B")
    tampered["payload"]["role"] = "MASTER"
    cases.append(("register_tampered", "/register", tampered))
    cases.append(("register_wrong_secret", "/register", registration(bad, "NODE-B")))
    cases.append(("register_expired", "/register", registration(good, "NODE-B", timestamp=time.time() - 3600)))
    cases.append(("register_future", "/register", registration(good, "NODE-B", timestamp=time.time() + 3600)))
    cases.append(("register_sender_mismatch", "/register", registration(good, "NODE-B", sender="NODE-X")))
    cases.append(("register_bad_role", "/register", registration(good, "NODE-B", role="KING")))
    cases.append(("register_wrong_type", "/register", registration(good, "NODE-B", message_type="HEARTBEAT")))
    missing = registration(good, "NODE-B")
    missing.pop("nonce")
    cases.append(("register_missing_field", "/register", missing))
    cases.append(("heartbeat_unregistered", "/heartbeat", heartbeat(good, "NODE-Z")))
    cases.append(("heartbeat_wrong_secret", "/heartbeat", heartbeat(bad, "NODE-A")))
    cases.append(("envelope_not_object", "/register", [1, 2, 3]))
    results = []
    for name, path, envelope in cases:
        r = post_json(port, path, envelope)
        results.append({"case": name, "status": r.get("status", r.get("error")), "body": r.get("json")})
    raw_cases = [
        ("invalid_json", "POST", "/register", b"{nope", None),
        ("bad_utf8", "POST", "/register", b"\xff\xfe\xfd", None),
        ("missing_length", "POST", "/register", None, {}),
        ("zero_length", "POST", "/register", b"", {"Content-Length": "0"}),
        ("oversized_length", "POST", "/register", b"{}", {"Content-Length": "70000"}),
        ("non_numeric_length", "POST", "/register", b"{}", {"Content-Length": "abc"}),
        ("post_unknown_path", "POST", "/admin", b"{}", None),
        ("get_peers", "GET", "/peers", None, None),
        ("get_unknown_path", "GET", "/status", None, None),
        # No body: stdlib answers 501 without reading a body, and on Windows the
        # unread bytes turn the close into a reset (same in both hubs).
        ("put_method", "PUT", "/peers", None, None),
        ("delete_method", "DELETE", "/peers", None, None),
    ]
    for name, method, path, body, headers in raw_cases:
        r = http_call(port, method, path, body, timeout=2.0, headers=headers)
        results.append({"case": name, "status": r.get("status", r.get("error")), "body": r.get("json")})
    return results


def oversized_header(target) -> dict[str, Any]:
    line = http_call(target.port, "GET", "/peers", timeout=2.0, headers={"X-Big": "a" * 70000})
    many = http_call(target.port, "GET", "/peers", timeout=2.0,
                     headers={f"X-H{i}": "1" for i in range(150)})
    return {"header_line_70k": line.get("status", line.get("error")),
            "headers_150": many.get("status", many.get("error"))}


def probe_port_sharing(target) -> dict[str, Any]:
    """Can another socket bind the hub's address while it is listening?"""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((LOOPBACK, target.port))
        return {"second_bind_allowed": True}
    except OSError as exc:
        return {"second_bind_allowed": False, "error": type(exc).__name__}
    finally:
        probe.close()


# ----------------------------------------------------------------------
# Node client compatibility (real NexusDistributedCore client methods)
# ----------------------------------------------------------------------

def make_node_client(hub_port: int, secret: str, node_id: str, role: str, web_port: int, tcp_port: int):
    """A NexusDistributedCore object WITHOUT __init__: no DB, no servers, no threads.

    Only the attributes its hub-client methods read are set, so
    ``post_envelope``/``build_*_envelope`` run exactly as in the runtime.
    """
    import nexus_distributed_core as core
    from nexus.compute.handlers import build_default_task_registry
    from nexus.compute.hardware import HardwareCapabilityDetector

    node = object.__new__(core.NexusDistributedCore)
    node.node_id = node_id
    node.role = role
    node.web_port = web_port
    node.tcp_port = tcp_port
    node.hub_url = f"http://{LOOPBACK}:{hub_port}"
    node.protocol = NexusProtocol(secret)
    node.compute_task_handlers = build_default_task_registry()
    node.hardware_capability_detector = HardwareCapabilityDetector()
    return node


def node_fetch_peers(node) -> dict[str, Any]:
    """Same call the polling loop makes (urllib, timeout=2)."""
    import urllib.request
    started = time.monotonic()
    try:
        with urllib.request.urlopen(f"{node.hub_url}/peers", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"ok": response.status == 200, "peers": data,
                    "elapsed_s": round(time.monotonic() - started, 3)}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "elapsed_s": round(time.monotonic() - started, 3)}


def probe_node_client(target, secret: str) -> dict[str, Any]:
    """Item 19: register + heartbeat + peers with the runtime's own client code."""
    a = make_node_client(target.port, secret, "NODE-A", "MASTER", 8081, 9091)
    c = make_node_client(target.port, secret, "NODE-C", "FOLLOWER", 8083, 9093)
    out = {
        "a_register": a.post_envelope("/register", a.build_registration_envelope()),
        "c_register": c.post_envelope("/register", c.build_registration_envelope()),
        "a_heartbeat": a.post_envelope("/heartbeat", a.build_heartbeat_envelope()),
        "c_heartbeat": c.post_envelope("/heartbeat", c.build_heartbeat_envelope()),
    }
    fetched = node_fetch_peers(c)
    peers = fetched.get("peers") or {}
    out["peers_ok"] = fetched["ok"]
    out["peer_ids"] = sorted(peers)
    out["record_keys"] = sorted(peers.get("NODE-A", {}))
    out["a_role"] = peers.get("NODE-A", {}).get("role")
    out["a_ip"] = peers.get("NODE-A", {}).get("ip")
    out["a_ports"] = [peers.get("NODE-A", {}).get("web_port"), peers.get("NODE-A", {}).get("tcp_port")]
    out["has_load_after_heartbeat"] = "load" in peers.get("NODE-A", {})
    return out


def probe_node_client_unavailable(target, secret: str, mode: str) -> dict[str, Any]:
    """Item 20: what the runtime client sees when the hub cannot serve it.

    mode: "blocked" (one idle client holds the server) or "closed" (port closed).
    """
    node = make_node_client(target.port, secret, "NODE-B", "FOLLOWER", 8082, 9092)
    if mode == "blocked":
        target.raw_connect()
        time.sleep(0.3)
    started = time.monotonic()
    ok = node.post_envelope("/register", node.build_registration_envelope())
    return {"mode": mode, "register_ok": ok, "elapsed_s": round(time.monotonic() - started, 3),
            "peers": {k: v for k, v in node_fetch_peers(node).items() if k != "peers"}}
