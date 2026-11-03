"""P1 regression: MASTER liveness must not depend on blocked sync.

With NEXUS_CLUSTER_SIZE > 1 distributed sync is fail-closed (QS-C01).
A FOLLOWER must still prove that the advertised MASTER is alive through
an authenticated, request-bound probe, and must not promote itself while
the legitimate MASTER is alive.
"""

import json
import socket
import threading
from unittest.mock import patch

import pytest

from nexus_distributed_core import NexusDistributedCore
from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache


SECRET = "test-shared-secret"
START = 1_000_000.0


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class ForbiddenPersistence:
    """Fails the test on any persistence access."""

    def __getattr__(self, name):
        raise AssertionError(f"persistence must not be used: {name}")


def make_core(
    node_id,
    role,
    *,
    cluster_size=3,
    secret=SECRET,
):
    core = object.__new__(NexusDistributedCore)
    core.node_id = node_id
    core.role = role
    core.protocol = NexusProtocol(secret)
    core.compute_message_ttl = 60.0
    core.liveness_replay_cache = ReplayCache()
    core.configured_cluster_size = cluster_size
    core.majority = cluster_size // 2 + 1
    core.persistence = ForbiddenPersistence()
    core.hub_url = "http://hub.invalid"
    core.peers = {}
    core.last_master_heartbeat = START
    return core


class ProbeServer:
    """Real TCP endpoint on loopback that dispatches to a core."""

    def __init__(self, core):
        self.core = core
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            conn.settimeout(2)
            self.core.handle_client(conn)

    def peer(self):
        return {
            "node_id": self.core.node_id,
            "role": "MASTER",
            "ip": "127.0.0.1",
            "tcp_port": self.port,
        }

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)
        self.sock.close()
        return False


def make_ack(master, request, *, role="MASTER", timestamp=None, **overrides):
    payload = {
        "role": role,
        "request_id": request["message_id"],
        "probe_sender": request["sender"],
    }
    payload.update(overrides.pop("payload", {}))
    return master.protocol.create_envelope(
        sender=overrides.pop("sender", master.node_id),
        message_type=overrides.pop("message_type", "MASTER_PROBE_ACK"),
        payload=payload,
        timestamp=timestamp,
    )


class FakeHubResponse:
    status = 200

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class StopPolling(BaseException):
    pass


def run_polling(core, peers, iterations=6):
    """Run the real polling loop with a fake clock (5 s per iteration)."""
    clock = {"t": START}
    count = {"n": 0}

    core.post_envelope = lambda path, envelope: True
    core.build_registration_envelope = lambda: {}
    core.build_heartbeat_envelope = lambda: {}
    core.shell_intake_loop = lambda: None

    def fake_sleep(_seconds):
        count["n"] += 1
        if count["n"] > iterations:
            raise StopPolling()
        clock["t"] += 5.0

    with (
        patch("nexus_distributed_core.time.sleep", side_effect=fake_sleep),
        patch(
            "nexus_distributed_core.time.time",
            side_effect=lambda: clock["t"],
        ),
        patch(
            "nexus_distributed_core.urllib.request.urlopen",
            return_value=FakeHubResponse(peers),
        ),
    ):
        with pytest.raises(StopPolling):
            core.async_polling_loop()

    return clock["t"]


def three_node_peers(master_peer=None):
    peers = {
        "NODE-B": {"node_id": "NODE-B", "role": "FOLLOWER"},
        "NODE-C": {"node_id": "NODE-C", "role": "FOLLOWER"},
    }
    if master_peer is not None:
        peers["NODE-A"] = master_peer
    return peers


def forbid_sync(core):
    def sync(_peer):
        raise AssertionError("sync_from_peer must not be called with N > 1")

    core.sync_from_peer = sync


# ----------------------------------------------------------------------
# Probe protocol (real TCP on loopback)
# ----------------------------------------------------------------------


def test_live_master_probe_succeeds():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")

    with ProbeServer(master) as server:
        assert follower.probe_master_liveness("NODE-A", server.peer())


def test_ex_master_answering_as_follower_is_rejected():
    ex_master = make_core("NODE-A", "FOLLOWER")
    follower = make_core("NODE-C", "FOLLOWER")

    with ProbeServer(ex_master) as server:
        with pytest.raises(ValueError, match="no longer holds MASTER"):
            follower.probe_master_liveness("NODE-A", server.peer())


def test_probe_with_wrong_shared_secret_fails():
    master = make_core("NODE-A", "MASTER", secret="other-secret")
    follower = make_core("NODE-C", "FOLLOWER")

    with ProbeServer(master) as server:
        # Master rejects the request signature and closes without reply.
        with pytest.raises((ConnectionError, OSError, ValueError)):
            follower.probe_master_liveness("NODE-A", server.peer())


def test_probe_to_unreachable_master_fails():
    follower = make_core("NODE-C", "FOLLOWER")

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()  # nothing listens on this port

    with pytest.raises(OSError):
        follower.probe_master_liveness(
            "NODE-A",
            {"ip": "127.0.0.1", "tcp_port": port},
        )


@pytest.mark.parametrize(
    "peer",
    [
        {"ip": "", "tcp_port": 9000},
        {"ip": "127.0.0.1", "tcp_port": 0},
        {"ip": "127.0.0.1", "tcp_port": 70000},
        {"ip": "127.0.0.1", "tcp_port": "abc"},
        "not-a-dict",
    ],
)
def test_probe_rejects_invalid_address(peer):
    follower = make_core("NODE-C", "FOLLOWER")

    with patch(
        "nexus_distributed_core.socket.create_connection"
    ) as connect:
        with pytest.raises(ValueError):
            follower.probe_master_liveness("NODE-A", peer)

    connect.assert_not_called()


# ----------------------------------------------------------------------
# ACK verification (HMAC, TTL, replay, identity, binding)
# ----------------------------------------------------------------------


def test_valid_ack_is_accepted():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    assert follower.verify_master_probe_ack(
        "NODE-A", request, make_ack(master, request)
    )


def test_ack_with_invalid_signature_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    ack = make_ack(master, request)
    ack["signature"] = "0" * 64

    with pytest.raises(ProtocolError):
        follower.verify_master_probe_ack("NODE-A", request, ack)


def test_ack_tampered_role_breaks_signature():
    ex_master = make_core("NODE-A", "FOLLOWER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    ack = make_ack(ex_master, request, role="FOLLOWER")
    ack["payload"]["role"] = "MASTER"

    with pytest.raises(ProtocolError):
        follower.verify_master_probe_ack("NODE-A", request, ack)


def test_expired_ack_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    import time

    ack = make_ack(master, request, timestamp=time.time() - 3600)

    with pytest.raises(ProtocolError, match="expired"):
        follower.verify_master_probe_ack("NODE-A", request, ack)


def test_replayed_ack_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")
    ack = make_ack(master, request)

    assert follower.verify_master_probe_ack("NODE-A", request, ack)

    with pytest.raises(ProtocolError, match="replay"):
        follower.verify_master_probe_ack("NODE-A", request, ack)


def test_concurrent_replay_of_same_ack_is_accepted_once():
    """Replay check must be atomic across threads."""
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")
    ack = make_ack(master, request)

    # Widen the check-then-add window so an unlocked implementation
    # deterministically accepts the same ACK more than once.
    import time

    cache = follower._liveness_replay_cache()
    original_contains = cache.contains_nonce  # last check before add()

    def slow_contains(*args, **kwargs):
        result = original_contains(*args, **kwargs)
        time.sleep(0.02)
        return result

    cache.contains_nonce = slow_contains

    workers = 16
    barrier = threading.Barrier(workers)
    accepted = []
    rejected = []

    def verify():
        barrier.wait()
        try:
            follower.verify_master_probe_ack("NODE-A", request, dict(ack))
            accepted.append(1)
        except ProtocolError:
            rejected.append(1)

    threads = [threading.Thread(target=verify) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(accepted) == 1
    assert len(rejected) == workers - 1


def test_liveness_verification_holds_lock():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    class RecordingLock:
        def __init__(self):
            self.entered = 0

        def __enter__(self):
            self.entered += 1

        def __exit__(self, *exc):
            return False

    follower.liveness_lock = RecordingLock()
    master.liveness_lock = RecordingLock()

    master.handle_master_probe(RecordingConnection(), request)
    follower.verify_master_probe_ack(
        "NODE-A", request, make_ack(master, request)
    )

    assert master.liveness_lock.entered == 1
    assert follower.liveness_lock.entered == 1


def test_ack_from_divergent_identity_is_rejected():
    impostor = make_core("NODE-X", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    with pytest.raises(ValueError, match="identity mismatch"):
        follower.verify_master_probe_ack(
            "NODE-A", request, make_ack(impostor, request)
        )


def test_ack_bound_to_another_request_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    old_request = follower.build_master_probe_envelope("NODE-A")
    new_request = follower.build_master_probe_envelope("NODE-A")

    with pytest.raises(ValueError, match="not bound to request"):
        follower.verify_master_probe_ack(
            "NODE-A", new_request, make_ack(master, old_request)
        )


def test_ack_bound_to_another_follower_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    ack = make_ack(master, request, payload={"probe_sender": "NODE-B"})

    with pytest.raises(ValueError, match="not bound to sender"):
        follower.verify_master_probe_ack("NODE-A", request, ack)


def test_ack_with_wrong_type_is_rejected():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    ack = make_ack(master, request, message_type="SYNC_BATCH")

    with pytest.raises(ValueError, match="response type"):
        follower.verify_master_probe_ack("NODE-A", request, ack)


# ----------------------------------------------------------------------
# Probe handler (MASTER side)
# ----------------------------------------------------------------------


class RecordingConnection:
    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)


def test_handler_rejects_probe_for_another_target():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    conn = RecordingConnection()

    with pytest.raises(ValueError, match="target mismatch"):
        master.handle_master_probe(
            conn, follower.build_master_probe_envelope("NODE-Z")
        )

    assert conn.sent == []


def test_handler_rejects_replayed_probe():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")

    master.handle_master_probe(RecordingConnection(), request)

    conn = RecordingConnection()
    with pytest.raises(ProtocolError, match="replay"):
        master.handle_master_probe(conn, request)

    assert conn.sent == []


def test_handler_rejects_unsigned_probe():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    request = follower.build_master_probe_envelope("NODE-A")
    request["signature"] = "f" * 64
    conn = RecordingConnection()

    with pytest.raises(ProtocolError):
        master.handle_master_probe(conn, request)

    assert conn.sent == []


def test_probe_is_dispatched_over_tcp_router():
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    conn = RecordingConnection()

    master.dispatch_tcp_message(
        conn, follower.build_master_probe_envelope("NODE-A")
    )

    assert len(conn.sent) == 1


# ----------------------------------------------------------------------
# Polling behavior with NEXUS_CLUSTER_SIZE = 3
# ----------------------------------------------------------------------


def test_n3_live_master_end_to_end_prevents_promotion():
    """The P1 scenario: real probe over TCP, MASTER alive for 30 s."""
    master = make_core("NODE-A", "MASTER")
    follower = make_core("NODE-C", "FOLLOWER")
    forbid_sync(follower)

    with ProbeServer(master) as server:
        end = run_polling(follower, three_node_peers(server.peer()))

    assert end - START >= 30.0  # well beyond the 15 s failover timeout
    assert follower.role == "FOLLOWER"
    assert follower.last_master_heartbeat == end


def test_n3_live_master_probe_prevents_promotion():
    follower = make_core("NODE-C", "FOLLOWER")
    forbid_sync(follower)
    probes = []
    follower.probe_master_liveness = (
        lambda master_id, peer: probes.append(master_id) or True
    )

    run_polling(
        follower,
        three_node_peers({"node_id": "NODE-A", "role": "MASTER"}),
    )

    assert follower.role == "FOLLOWER"
    assert probes == ["NODE-A"] * 6


def test_n3_unreachable_advertised_master_allows_failover():
    """Hub advertisement alone must not suppress failover."""
    follower = make_core("NODE-C", "FOLLOWER")
    forbid_sync(follower)

    def unreachable(_master_id, _peer):
        raise ConnectionError("master down")

    follower.probe_master_liveness = unreachable

    run_polling(
        follower,
        three_node_peers({"node_id": "NODE-A", "role": "MASTER"}),
    )

    assert follower.role == "MASTER"


def test_n3_ex_master_answering_as_follower_allows_failover():
    ex_master = make_core("NODE-A", "FOLLOWER")
    follower = make_core("NODE-C", "FOLLOWER")
    forbid_sync(follower)

    with ProbeServer(ex_master) as server:
        run_polling(follower, three_node_peers(server.peer()))

    assert follower.role == "MASTER"


def test_n3_no_quorum_blocks_promotion():
    follower = make_core("NODE-C", "FOLLOWER")
    forbid_sync(follower)
    follower.probe_master_liveness = lambda *_: pytest.fail(
        "no MASTER advertised, probe must not run"
    )

    run_polling(
        follower,
        {"NODE-C": {"node_id": "NODE-C", "role": "FOLLOWER"}},
    )

    assert follower.role == "FOLLOWER"


def test_n3_lower_id_follower_defers_promotion():
    follower = make_core("NODE-B", "FOLLOWER")
    forbid_sync(follower)

    def unreachable(_master_id, _peer):
        raise ConnectionError("master down")

    follower.probe_master_liveness = unreachable

    run_polling(
        follower,
        three_node_peers({"node_id": "NODE-A", "role": "MASTER"}),
    )

    assert follower.role == "FOLLOWER"  # NODE-C is the candidate


# ----------------------------------------------------------------------
# Legacy N = 1 behavior
# ----------------------------------------------------------------------


def test_n1_keeps_legacy_sync_liveness_path():
    follower = make_core("NODE-C", "FOLLOWER", cluster_size=1)
    syncs = []
    follower.sync_from_peer = lambda peer: syncs.append(peer) or 0
    follower.probe_master_liveness = lambda *_: pytest.fail(
        "N == 1 must keep the legacy sync path"
    )

    run_polling(
        follower,
        three_node_peers({"node_id": "NODE-A", "role": "MASTER"}),
    )

    assert follower.role == "FOLLOWER"
    assert len(syncs) == 6
