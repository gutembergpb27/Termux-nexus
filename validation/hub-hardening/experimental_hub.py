"""Experimental hardened Nexus Hub (W07).

Isolated prototype. It does NOT replace ``nexus_rendezvous.py`` and is not
wired into the runtime. Validation logic (envelope verification, REGISTER and
HEARTBEAT rules, capability/load normalization) is imported unchanged from the
original module, so the HMAC contract is the same code, not a copy.

What changes versus the original hub:
- concurrent handling (one thread per connection, bounded by a slot limit);
- explicit per-socket timeout plus a whole-request deadline (anti slow-drip);
- fast 503 rejection when at capacity, optional client allowlist (403);
- bind host is configurable; default 127.0.0.1; wildcard needs opt-in;
- exclusive port bind on Windows (no SO_REUSEADDR port sharing);
- shared state (peers, replay cache) guarded by one lock;
- stoppable reaper that survives exceptions;
- controlled shutdown that closes pending connections and joins threads;
- unexpected exceptions return 500 without traceback; counters for events.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import queue
import signal
import socket
import sys
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import nexus_rendezvous as original  # noqa: E402  (validation logic, unchanged)
from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache  # noqa: E402

HUB_VERSION = "w07-exp-1"
WILDCARD_HOSTS = {"0.0.0.0", "::", ""}
ORIGINAL_MAX_BODY = 65536
REJECT_QUEUE_SIZE = 64   # pending 403/503 responses; beyond this, plain close
REJECT_DRAIN_S = 0.2     # per rejected connection, in the rejecter thread

logger = logging.getLogger("nexus.hub.experimental")


@dataclass(frozen=True)
class HubLimits:
    max_connections: int = 32
    max_per_client: int = 8
    socket_timeout_s: float = 5.0
    request_deadline_s: float = 10.0
    max_body_bytes: int = ORIGINAL_MAX_BODY
    shutdown_grace_s: float = 2.0
    peer_timeout_s: float = float(original.PEER_TIMEOUT)
    message_ttl_s: float = float(original.MESSAGE_TTL)
    reap_interval_s: float = 5.0
    listen_backlog: int = 128

    def validate(self) -> None:
        if not 1 <= self.max_connections <= 1024:
            raise ValueError("max_connections must be within 1..1024")
        if not 1 <= self.max_per_client <= self.max_connections:
            raise ValueError("max_per_client must be within 1..max_connections")
        if not 0 < self.socket_timeout_s <= 30:
            raise ValueError("socket_timeout_s must be within (0, 30]")
        if not self.socket_timeout_s <= self.request_deadline_s <= 60:
            raise ValueError("request_deadline_s must be >= socket_timeout_s and <= 60")
        # Never accept larger bodies than the original hub.
        if not 1 <= self.max_body_bytes <= ORIGINAL_MAX_BODY:
            raise ValueError("max_body_bytes must be within 1..65536")
        if not 0 < self.shutdown_grace_s <= 30:
            raise ValueError("shutdown_grace_s must be within (0, 30]")
        if self.peer_timeout_s <= 0 or self.message_ttl_s <= 0 or self.reap_interval_s <= 0:
            raise ValueError("timeouts must be positive")
        if not 1 <= self.listen_backlog <= 4096:
            raise ValueError("listen_backlog must be within 1..4096")


class HubStats:
    """Thread-safe event counters. Never records payloads or secrets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()

    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[name] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)


def _parse_networks(values) -> tuple:
    networks = []
    for value in values or ():
        networks.append(ipaddress.ip_network(str(value), strict=False))
    return tuple(networks)


def _json_response(status: int, payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    reason = {403: "Forbidden", 503: "Service Unavailable"}.get(status, "Error")
    head = (
        f"HTTP/1.0 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    return head + body


class HardenedHubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # one request per connection, like the original
    server_version = "NexusHubExperimental/" + HUB_VERSION

    def setup(self) -> None:
        self.timeout = self.server.limits.socket_timeout_s
        super().setup()

    # BaseHTTPRequestHandler logs to stderr with client data; route to counters.
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return

    def log_error(self, format, *args):  # noqa: A002 - stdlib signature
        if format.startswith("Request timed out"):
            self.server.stats.incr("socket_timeout")
            logger.info("hub_event=socket_timeout")
        else:
            self.server.stats.incr("http_protocol_error")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.stats.incr(f"status_{status}")

    # Set to False by do_POST until the request body has been read.
    _body_consumed = True

    def finish(self) -> None:
        super().finish()
        if not self._body_consumed and not self.server._closing.is_set():
            self._drain_unread_body()

    def _drain_unread_body(self) -> None:
        """Half-close, then briefly read leftover request bytes so close() does not RST.

        Same bounds as the admission rejecter; skipped while shutting down.
        """
        try:
            self.connection.shutdown(socket.SHUT_WR)
            deadline = time.monotonic() + REJECT_DRAIN_S
            received = 0
            while received < 65536:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.connection.settimeout(remaining)
                chunk = self.connection.recv(4096)
                if not chunk:
                    break
                received += len(chunk)
        except OSError:
            pass

    def do_POST(self):
        self._body_consumed = False
        self._guarded(self._do_post, "post")

    def do_GET(self):
        self._guarded(self._do_get, "get")

    def _guarded(self, action, where: str) -> None:
        try:
            action()
        except TimeoutError:
            self.server.stats.incr("socket_timeout")
            self.close_connection = True
        except OSError:
            # Client vanished or the connection was cut by the deadline.
            self.server.stats.incr("client_io_error")
            self.close_connection = True
        except Exception as exc:  # never leak a traceback; keep serving
            self._internal_error(where, exc)

    def _internal_error(self, where: str, exc: BaseException) -> None:
        self.server.stats.incr("handler_error")
        logger.warning("hub_event=handler_error where=%s error_type=%s", where, type(exc).__name__)
        try:
            self._send_json(500, {"error": "internal error"})
        except OSError:
            pass

    def _do_post(self) -> None:
        server = self.server
        if self.path not in {"/register", "/heartbeat"}:
            self._send_json(404, {"error": "not found"})
            return
        if server.protocol is None:
            self._send_json(503, {"error": "protocol not configured"})
            return
        try:
            raw_length = self.headers.get("Content-Length", "")
            content_length = int(raw_length)
            if content_length <= 0 or content_length > server.limits.max_body_bytes:
                raise ValueError("invalid content length")
            post_data = self.rfile.read(content_length)
            self._body_consumed = True
            if len(post_data) != content_length:
                server.stats.incr("incomplete_body")
                raise ValueError("incomplete body")
            envelope = json.loads(post_data.decode("utf-8"))
            if not isinstance(envelope, dict):
                raise ValueError("invalid JSON envelope")
            client_ip = self.client_address[0]
            with server.state_lock:
                now = time.time()
                if self.path == "/register":
                    record = original.register_peer(
                        envelope=envelope,
                        client_ip=client_ip,
                        protocol=server.protocol,
                        replay_cache=server.replay_cache,
                        peers=server.peers,
                        now=now,
                        ttl=server.limits.message_ttl_s,
                    )
                    response_status = "registered"
                else:
                    record = original.update_peer_heartbeat(
                        envelope=envelope,
                        protocol=server.protocol,
                        replay_cache=server.replay_cache,
                        peers=server.peers,
                        now=now,
                        ttl=server.limits.message_ttl_s,
                    )
                    response_status = "alive"
                result = {
                    "status": response_status,
                    "node_id": record["node_id"],
                    "detected_ip": record["ip"],
                }
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return
        except ProtocolError as exc:
            server.stats.incr("auth_rejected")
            self._send_json(401, {"error": str(exc)})
            return
        except OSError:
            raise  # handled by _guarded (timeouts, cut connections)
        except (TypeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        server.stats.incr(f"accepted_{response_status}")
        self._send_json(200, result)

    def _do_get(self) -> None:
        if self.path != "/peers":
            # Original sends no response at all here; a JSON 404 is safer.
            self._send_json(404, {"error": "not found"})
            return
        server = self.server
        with server.state_lock:
            now = time.time()
            active = {
                key: dict(value)
                for key, value in server.peers.items()
                if now - value.get("last_seen", 0) < server.limits.peer_timeout_s
            }
        self._send_json(200, active)


class HardenedHub(ThreadingHTTPServer):
    """Bounded, stoppable hub server. Use ``start()`` and ``close()``."""

    daemon_threads = True  # threads are tracked and joined by close()
    block_on_close = False
    allow_reuse_address = False

    def __init__(
        self,
        secret: str | None,
        *,
        host: str = "127.0.0.1",
        port: int = 8500,
        limits: HubLimits | None = None,
        allow_wildcard: bool = False,
        allowed_networks=(),
    ) -> None:
        self.limits = limits or HubLimits()
        self.limits.validate()
        if host in WILDCARD_HOSTS and not allow_wildcard:
            raise ValueError("wildcard bind requires allow_wildcard=True")
        if not 0 <= int(port) <= 65535:
            raise ValueError("invalid port")
        self.request_queue_size = self.limits.listen_backlog
        self.protocol = NexusProtocol(secret) if secret else None
        self.allowed_networks = _parse_networks(allowed_networks)
        self.peers: dict[str, dict[str, Any]] = {}
        self.replay_cache = ReplayCache()
        self.state_lock = threading.Lock()
        self.stats = HubStats()
        self._slots = threading.BoundedSemaphore(self.limits.max_connections)
        self._active: dict[socket.socket, float] = {}
        self._per_client: Counter[str] = Counter()
        self._workers: set[threading.Thread] = set()
        self._track_lock = threading.Lock()
        self._closing = threading.Event()
        self._reject_queue: queue.Queue = queue.Queue(maxsize=REJECT_QUEUE_SIZE)
        self._service_threads: list[threading.Thread] = []
        self._close_report: dict[str, Any] | None = None
        super().__init__((host, int(port)), HardenedHubHandler)

    # -- socket setup -------------------------------------------------
    def server_bind(self) -> None:
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        # Skip HTTPServer.server_bind's getfqdn() (slow reverse DNS).
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        self.server_name = str(self.server_address[0])
        self.server_port = self.server_address[1]

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    # -- admission ----------------------------------------------------
    def _client_allowed(self, client_address) -> bool:
        if not self.allowed_networks:
            return True
        try:
            address = ipaddress.ip_address(client_address[0])
        except ValueError:
            return False
        return any(address in network for network in self.allowed_networks)

    def _reject(self, request: socket.socket, status: int, message: str, counter: str) -> None:
        """Hand the rejection to the rejecter thread; never block the accept loop."""
        self.stats.incr(counter)
        logger.info("hub_event=%s", counter)
        try:
            self._reject_queue.put_nowait((request, _json_response(status, {"error": message})))
        except queue.Full:
            self.stats.incr("rejected_dropped")
            request.close()

    def _rejecter(self) -> None:
        """Send the short error response, then drain briefly so close() does not RST."""
        while True:
            try:
                request, response = self._reject_queue.get(timeout=0.1)
            except queue.Empty:
                if self._closing.is_set():
                    return
                continue
            if self._closing.is_set():
                request.close()  # shutting down: no drain, keep close() bounded
                continue
            self._finish_reject(request, response)

    def _finish_reject(self, request: socket.socket, response: bytes) -> None:
        try:
            request.settimeout(0.2)
            request.sendall(response)
            request.shutdown(socket.SHUT_WR)
            deadline = time.monotonic() + REJECT_DRAIN_S
            received = 0
            while time.monotonic() < deadline and received < 65536:
                chunk = request.recv(4096)
                if not chunk:
                    break
                received += len(chunk)
        except OSError:
            pass
        finally:
            request.close()

    def process_request(self, request, client_address):
        self.stats.incr("connections_accepted")
        if self._closing.is_set():
            self._reject(request, 503, "hub shutting down", "rejected_shutdown")
            return
        if not self._client_allowed(client_address):
            self._reject(request, 403, "client not allowed", "rejected_client")
            return
        client = str(client_address[0])
        with self._track_lock:
            over_client_limit = self._per_client[client] >= self.limits.max_per_client
            if not over_client_limit:
                self._per_client[client] += 1
        if over_client_limit:
            self._reject(request, 503, "too many connections from client", "rejected_client_limit")
            return
        if not self._slots.acquire(blocking=False):
            self._release_client(client)
            self._reject(request, 503, "hub at capacity", "rejected_capacity")
            return
        thread = threading.Thread(
            target=self._worker,
            args=(request, client_address),
            name="hub-conn",
            daemon=True,
        )
        with self._track_lock:
            self._active[request] = time.monotonic()
            self._workers.add(thread)
        try:
            thread.start()
        except RuntimeError:
            with self._track_lock:
                self._active.pop(request, None)
                self._workers.discard(thread)
            self._slots.release()
            self._release_client(client)
            self._reject(request, 503, "hub at capacity", "rejected_thread_start")

    def _release_client(self, client: str) -> None:
        with self._track_lock:
            self._per_client[client] -= 1
            if self._per_client[client] <= 0:
                del self._per_client[client]

    def _worker(self, request, client_address) -> None:
        try:
            self.finish_request(request, client_address)
        except Exception as exc:
            self.stats.incr("connection_error")
            logger.info("hub_event=connection_error error_type=%s", type(exc).__name__)
        finally:
            with self._track_lock:
                self._active.pop(request, None)
                self._workers.discard(threading.current_thread())
            try:
                self.shutdown_request(request)
            finally:
                self._slots.release()
                self._release_client(str(client_address[0]))

    def handle_error(self, request, client_address):  # no traceback to stderr
        self.stats.incr("connection_error")

    # -- background services ------------------------------------------
    def _janitor(self) -> None:
        """Close connections that exceed the whole-request deadline."""
        while not self._closing.wait(0.1):
            limit = time.monotonic() - self.limits.request_deadline_s
            with self._track_lock:
                expired = [sock for sock, started in self._active.items() if started < limit]
                for sock in expired:
                    self._active[sock] = float("inf")  # cut once
            for sock in expired:
                self.stats.incr("deadline_closed")
                logger.info("hub_event=deadline_closed")
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _reaper(self) -> None:
        while not self._closing.wait(self.limits.reap_interval_s):
            try:
                self.reap_once()
            except Exception as exc:
                self.stats.incr("reaper_error")
                logger.warning("hub_event=reaper_error error_type=%s", type(exc).__name__)

    def reap_once(self, now: float | None = None) -> int:
        with self.state_lock:
            current = time.time() if now is None else now
            expired = [
                key for key, value in self.peers.items()
                if current - value.get("last_seen", 0) >= self.limits.peer_timeout_s
            ]
            for key in expired:
                del self.peers[key]
        if expired:
            self.stats.incr("peers_reaped", len(expired))
        return len(expired)

    def start(self) -> "HardenedHub":
        for target, name in (
            (lambda: self.serve_forever(poll_interval=0.1), "hub-serve"),
            (self._janitor, "hub-janitor"),
            (self._reaper, "hub-reaper"),
            (self._rejecter, "hub-rejecter"),
        ):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._service_threads.append(thread)
        logger.info("hub_event=started host=%s port=%s", self.server_address[0], self.port)
        return self

    # -- shutdown -----------------------------------------------------
    def close(self) -> dict[str, Any]:
        """Stop accepting, finish or cut pending connections, join threads."""
        if self._close_report is not None:
            return self._close_report
        started = time.monotonic()
        grace = self.limits.shutdown_grace_s
        self._closing.set()
        if self._service_threads:
            self.shutdown()  # serve_forever exits within poll_interval
        self.server_close()
        # Let in-flight requests finish, then cut whatever remains.
        soft_deadline = started + grace / 2
        while time.monotonic() < soft_deadline and self.active_connections():
            time.sleep(0.02)
        with self._track_lock:
            remaining = list(self._active)
        forced = 0
        for sock in remaining:
            forced += 1
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        hard_deadline = started + grace
        with self._track_lock:
            workers = list(self._workers)
        for thread in workers + self._service_threads:
            thread.join(max(0.0, hard_deadline - time.monotonic()))
        alive = [t.name for t in workers + self._service_threads if t.is_alive()]
        self._close_report = {
            "duration_s": round(time.monotonic() - started, 3),
            "forced_connections": forced,
            "threads_alive": alive,
            "clean": not alive,
        }
        logger.info("hub_event=closed clean=%s forced=%s", not alive, forced)
        return self._close_report

    def active_connections(self) -> int:
        with self._track_lock:
            return len(self._active)

    def __enter__(self) -> "HardenedHub":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()


def limits_dict(limits: HubLimits) -> dict[str, Any]:
    return asdict(limits)


# ----------------------------------------------------------------------
# CLI (not used by the runtime; for isolated manual experiments only)
# ----------------------------------------------------------------------

class _StopRequested(Exception):
    pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Experimental hardened Nexus Hub (W07, isolated)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8500)
    parser.add_argument("--allow-wildcard", action="store_true",
                        help="required to bind 0.0.0.0 / ::")
    parser.add_argument("--allow-network", action="append", default=[],
                        help="client allowlist (CIDR); repeatable; empty = any client that reaches the bind")
    parser.add_argument("--max-connections", type=int, default=HubLimits.max_connections)
    parser.add_argument("--socket-timeout", type=float, default=HubLimits.socket_timeout_s)
    parser.add_argument("--request-deadline", type=float, default=HubLimits.request_deadline_s)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    secret = os.getenv("NEXUS_SECRET_KEY", "").strip()
    if not secret:
        print("hub_error=missing_secret", flush=True)
        return 2
    try:
        limits = HubLimits(
            max_connections=args.max_connections,
            socket_timeout_s=args.socket_timeout,
            request_deadline_s=args.request_deadline,
        )
        hub = HardenedHub(
            secret,
            host=args.host,
            port=args.port,
            limits=limits,
            allow_wildcard=args.allow_wildcard,
            allowed_networks=args.allow_network,
        )
    except (ValueError, OSError) as exc:
        print(f"hub_error=config error_type={type(exc).__name__}", flush=True)
        return 2
    del secret

    def _on_signal(signum, _frame):
        raise _StopRequested(signum)

    for name in ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, _on_signal)

    hub.start()
    print(f"hub_listening host={hub.server_address[0]} port={hub.port} version={HUB_VERSION}", flush=True)
    try:
        while True:
            time.sleep(0.2)
    except (_StopRequested, KeyboardInterrupt):
        pass
    report = hub.close()
    print(f"hub_closed clean={report['clean']} forced={report['forced_connections']} "
          f"stats={json.dumps(hub.stats.snapshot(), sort_keys=True)}", flush=True)
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
