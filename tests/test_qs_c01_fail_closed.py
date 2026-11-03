"""QS-C01: distributed sync and writes stay fail-closed for N != 1."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message
from persistence import NexusPersistence


class RecordingPersistence:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append(name)
            return "0" * 64

        return record


class RecordingConnection:
    def __init__(self, incoming=None):
        self._incoming = encode_message(incoming) if incoming else b""
        self.sent = []

    def recv(self, size):
        chunk = self._incoming[:size]
        self._incoming = self._incoming[size:]
        return chunk

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        pass


def make_core(cluster_size=3, persistence=None, role="MASTER"):
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    core.role = role
    core.configured_cluster_size = cluster_size
    core.persistence = (
        persistence if persistence is not None else RecordingPersistence()
    )
    return core


PEER = {"node_id": "NODE-B", "ip": "127.0.0.1", "tcp_port": 9001}


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "size,enabled",
    [
        (1, True),
        (2, False),
        (3, False),
        (5, False),
        ("1", False),   # non-int fails closed
        (True, False),  # bool is not int for this purpose
        (1.0, False),
        (None, False),
    ],
)
def test_sync_enabled_only_for_single_member(size, enabled):
    core = make_core(cluster_size=size)
    assert core._distributed_sync_enabled() is enabled


def test_missing_cluster_size_fails_closed():
    core = object.__new__(NexusDistributedCore)
    assert core._distributed_sync_enabled() is False


# ----------------------------------------------------------------------
# Sync blocked with N = 3
# ----------------------------------------------------------------------


def test_n3_sync_from_peer_blocked_without_network():
    core = make_core()

    with patch(
        "nexus_distributed_core.socket.create_connection"
    ) as connect:
        with pytest.raises(RuntimeError, match="quorum commit"):
            core.sync_from_peer(PEER)

    connect.assert_not_called()
    assert core.persistence.calls == []


def test_n3_handle_sync_batch_blocked():
    core = make_core()

    with pytest.raises(RuntimeError, match="quorum commit"):
        core.handle_sync_batch(
            RecordingConnection(),
            {"type": "SYNC_BATCH", "blocks": [{"x": 1}]},
        )

    assert core.persistence.calls == []


def test_n3_handle_state_summary_blocked():
    core = make_core()
    conn = RecordingConnection()

    with pytest.raises(RuntimeError, match="quorum commit"):
        core.handle_state_summary(
            conn,
            {"type": "STATE_SUMMARY", "payload": {"height": 0}},
        )

    assert core.persistence.calls == []
    assert conn.sent == []


def test_n3_state_summary_over_tcp_router_sends_nothing():
    core = make_core()
    conn = RecordingConnection(
        {"type": "STATE_SUMMARY", "payload": {"height": 0}}
    )

    core.handle_client(conn)  # logs the block, never raises

    assert conn.sent == []
    assert core.persistence.calls == []


# ----------------------------------------------------------------------
# Writes blocked with N = 3
# ----------------------------------------------------------------------


def run_intake(core, inputs):
    feed = iter(inputs)

    def fake_input(_prompt):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    with patch("builtins.input", side_effect=fake_input):
        core.shell_intake_loop()


def test_n3_intake_blocks_write_with_explicit_feedback(capsys):
    core = make_core()

    run_intake(core, ["payload-1", "payload-2"])

    assert core.persistence.calls == []
    out = capsys.readouterr().out
    assert out.count("Escrita BLOQUEADA") == 2
    assert "NEXUS_CLUSTER_SIZE=3" in out
    assert "Payload não persistido" in out


def test_intake_blocks_write_after_role_change(capsys):
    core = make_core(cluster_size=1)

    def fake_input(_prompt):
        if core.persistence.calls or getattr(core, "_asked", False):
            raise EOFError
        core._asked = True
        core.role = "FOLLOWER"  # demoted while waiting for input
        return "payload"

    with patch("builtins.input", side_effect=fake_input):
        core.shell_intake_loop()

    assert core.persistence.calls == []
    assert "não é mais MASTER" in capsys.readouterr().out


def test_n1_intake_keeps_legacy_write(capsys):
    core = make_core(cluster_size=1)

    run_intake(core, ["payload-1"])

    assert core.persistence.calls == ["append_transaction"]
    assert "BLOQUEADA" not in capsys.readouterr().out


# ----------------------------------------------------------------------
# Persistent data preservation (real store on tmp_path)
# ----------------------------------------------------------------------


def digest_dir(path: Path):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.iterdir())
        if p.is_file()
    }


def test_n3_blocked_operations_preserve_persistent_data(tmp_path):
    store_dir = tmp_path / "store"
    store = NexusPersistence(filepath=str(store_dir / "nexus.db"))
    store.append_transaction({"event": "BEFORE", "n": 1})
    store.append_transaction({"event": "BEFORE", "n": 2})

    before = digest_dir(store_dir)
    last_hash = store.last_hash
    assert before

    core = make_core(persistence=store)

    with pytest.raises(RuntimeError):
        core.handle_sync_batch(None, {"blocks": [{"forged": True}]})

    with pytest.raises(RuntimeError):
        core.handle_state_summary(
            RecordingConnection(), {"payload": {"height": 0}}
        )

    with pytest.raises(RuntimeError):
        core.sync_from_peer(PEER)

    run_intake(core, ["must-not-persist"])

    assert digest_dir(store_dir) == before
    assert store.last_hash == last_hash
    assert store.validate_chain()
