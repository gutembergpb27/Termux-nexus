"""W08-B / PR-B: explicit, fail-closed cluster mode.

Behavioral coverage for:
1. missing configuration blocks unsafe operations;
2. invalid configuration fails safely (refuses to start);
3. explicit single mode never enables distributed sync;
4. distributed mode keeps writes blocked;
5. hub peer visibility never authorizes writes or sync (pre-existing
   distributed promotion still counts hub-visible members, but the
   resulting MASTER role carries no write authority);
6. QS-C01 is not weakened;
7. existing data stays readable and unchanged;
8. distributed consensus is not enabled.
"""

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus_cluster_mode import (
    MODE_DISTRIBUTED,
    MODE_SINGLE,
    MODE_UNCONFIGURED,
    resolve_cluster_mode,
)
from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message
from persistence import NexusPersistence


START = 1_000_000.0
PEER = {"node_id": "NODE-B", "ip": "127.0.0.1", "tcp_port": 9001}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


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
        self.closed = False

    def recv(self, size):
        chunk = self._incoming[:size]
        self._incoming = self._incoming[size:]
        return chunk

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def core_from_env(env, *, role="MASTER", peers=None, persistence=None):
    """Bare core whose cluster fields come from the real resolver."""
    cluster = resolve_cluster_mode(env)
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    core.role = role
    core.cluster_mode = cluster.mode
    core.configured_cluster_size = cluster.cluster_size
    core.majority = cluster.majority
    core.peers = dict(peers or {})
    core.persistence = (
        persistence if persistence is not None else RecordingPersistence()
    )
    return core


def run_intake(core, inputs):
    feed = iter(inputs)

    def fake_input(_prompt):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    with patch("builtins.input", side_effect=fake_input):
        core.shell_intake_loop()


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
    """Run the real polling loop with a fake clock and a fake hub."""
    clock = {"t": START}
    count = {"n": 0}

    core.hub_url = "http://hub.invalid"
    core.last_master_heartbeat = START
    core.post_envelope = lambda path, envelope: True
    core.build_registration_envelope = lambda: {}
    core.build_heartbeat_envelope = lambda: {}
    core.shell_intake_loop = lambda: None

    def forbidden_sync(_peer):
        raise AssertionError("legacy sync must stay disabled")

    def unreachable(_master_id, _peer):
        raise ConnectionError("master down")

    core.sync_from_peer = forbidden_sync
    core.probe_master_liveness = unreachable

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
        patch("nexus_distributed_core.threading.Thread"),
    ):
        with pytest.raises(StopPolling):
            core.async_polling_loop()


def full_hub_view(*, with_dead_master=True):
    """Hub listing that 'shows' every member of a 3-node cluster.

    NODE-A (the core under test) is the greatest follower id, so it is
    always the promotion candidate and only the gates decide.
    """
    peers = {
        "NODE-A": {"node_id": "NODE-A", "role": "FOLLOWER"},
        "NODE-1": {"node_id": "NODE-1", "role": "FOLLOWER"},
    }
    if with_dead_master:
        peers["NODE-0"] = {"node_id": "NODE-0", "role": "MASTER"}
    else:
        peers["NODE-0"] = {"node_id": "NODE-0", "role": "FOLLOWER"}
    return peers


# ----------------------------------------------------------------------
# Resolver: valid configurations
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "env,mode,size,majority,writes",
    [
        ({}, MODE_UNCONFIGURED, None, None, False),
        ({"NEXUS_CLUSTER_SIZE": "1"}, MODE_UNCONFIGURED, 1, None, False),
        ({"NEXUS_CLUSTER_SIZE": "  "}, MODE_UNCONFIGURED, None, None, False),
        ({"NEXUS_CLUSTER_MODE": ""}, MODE_UNCONFIGURED, None, None, False),
        ({"NEXUS_CLUSTER_SIZE": "3"}, MODE_DISTRIBUTED, 3, 2, False),
        ({"NEXUS_CLUSTER_MODE": "single"}, MODE_SINGLE, 1, 1, True),
        (
            {"NEXUS_CLUSTER_MODE": " Single ", "NEXUS_CLUSTER_SIZE": "1"},
            MODE_SINGLE, 1, 1, True,
        ),
        (
            {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "2"},
            MODE_DISTRIBUTED, 2, 2, False,
        ),
        (
            {"NEXUS_CLUSTER_MODE": "DISTRIBUTED", "NEXUS_CLUSTER_SIZE": "5"},
            MODE_DISTRIBUTED, 5, 3, False,
        ),
    ],
)
def test_resolver_valid_configurations(env, mode, size, majority, writes):
    cluster = resolve_cluster_mode(env)

    assert cluster.mode == mode
    assert cluster.cluster_size == size
    assert cluster.majority == majority
    assert cluster.local_writes_allowed is writes
    assert cluster.promotion_allowed is (majority is not None)


def test_resolver_never_reads_hub_or_peer_data():
    """Only the two cluster variables matter; peer keys are ignored."""
    noisy = {
        "NEXUS_CLUSTER_SIZE": "1",
        "NEXUS_PEERS": "NODE-B,NODE-C",
        "NEXUS_HUB_URL": "http://hub.invalid",
    }
    assert resolve_cluster_mode(noisy).mode == MODE_UNCONFIGURED


# ----------------------------------------------------------------------
# Resolver: invalid configurations fail safely
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "env,match",
    [
        ({"NEXUS_CLUSTER_SIZE": "0"}, "NEXUS_CLUSTER_SIZE"),
        ({"NEXUS_CLUSTER_SIZE": "-1"}, "NEXUS_CLUSTER_SIZE"),
        ({"NEXUS_CLUSTER_SIZE": "abc"}, "NEXUS_CLUSTER_SIZE"),
        ({"NEXUS_CLUSTER_SIZE": "3.0"}, "NEXUS_CLUSTER_SIZE"),
        ({"NEXUS_CLUSTER_SIZE": "+3"}, "NEXUS_CLUSTER_SIZE"),
        ({"NEXUS_CLUSTER_MODE": "solo"}, "NEXUS_CLUSTER_MODE"),
        ({"NEXUS_CLUSTER_MODE": "auto"}, "NEXUS_CLUSTER_MODE"),
        (
            {"NEXUS_CLUSTER_MODE": "single", "NEXUS_CLUSTER_SIZE": "3"},
            "conflicts",
        ),
        ({"NEXUS_CLUSTER_MODE": "distributed"}, "requires"),
        (
            {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "1"},
            "requires",
        ),
    ],
)
def test_resolver_rejects_invalid_configuration(env, match):
    with pytest.raises(ValueError, match=match):
        resolve_cluster_mode(env)


def test_invalid_configuration_refuses_start_before_side_effects(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEXUS_SECRET_KEY", "w08b-test-key")
    monkeypatch.setenv("NEXUS_CLUSTER_MODE", "single")
    monkeypatch.setenv("NEXUS_CLUSTER_SIZE", "3")
    monkeypatch.setenv("NEXUS_DB_PATH", str(tmp_path / "store" / "n.db"))

    with (
        patch("nexus_distributed_core.start_web_server") as web,
        patch("nexus_distributed_core.threading.Thread") as thread,
    ):
        with pytest.raises(ValueError, match="conflicts"):
            NexusDistributedCore("NODE-A", 8081, 9091, "MASTER")

    web.assert_not_called()
    thread.assert_not_called()
    assert list(tmp_path.iterdir()) == []


# ----------------------------------------------------------------------
# Requirement 1: missing configuration blocks unsafe operations
# ----------------------------------------------------------------------


def test_missing_configuration_blocks_writes(capsys):
    core = core_from_env({})

    run_intake(core, ["payload"])

    assert core.persistence.calls == []
    out = capsys.readouterr().out
    assert "cluster_mode_unconfigured" in out
    assert "Payload não persistido" in out


def test_old_default_n1_without_mode_blocks_writes(capsys):
    """The exact pre-W08-B default no longer writes."""
    core = core_from_env({"NEXUS_CLUSTER_SIZE": "1"})

    run_intake(core, ["payload"])

    assert core.persistence.calls == []
    assert "cluster_mode_unconfigured" in capsys.readouterr().out


def assert_promotion_gate_fired(caplog):
    """The W08-B gate decided, not an incidental polling error."""
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        m.startswith("leadership_promotion_blocked_cluster_mode")
        for m in messages
    ), messages
    assert not any(m.startswith("polling_error") for m in messages)


def test_missing_configuration_never_promotes(caplog):
    core = core_from_env({}, role="FOLLOWER")

    with caplog.at_level("WARNING", logger="nexus.core"):
        run_polling(core, full_hub_view())

    assert core.role == "FOLLOWER"
    assert_promotion_gate_fired(caplog)


def test_old_default_n1_without_mode_never_promotes(caplog):
    """Pre-W08-B: majority 1 let any follower promote alone."""
    core = core_from_env({"NEXUS_CLUSTER_SIZE": "1"}, role="FOLLOWER")

    with caplog.at_level("WARNING", logger="nexus.core"):
        run_polling(core, {})

    assert core.role == "FOLLOWER"
    assert_promotion_gate_fired(caplog)


def test_missing_configuration_still_starts_for_reads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEXUS_SECRET_KEY", "w08b-test-key")
    monkeypatch.delenv("NEXUS_CLUSTER_MODE", raising=False)
    monkeypatch.delenv("NEXUS_CLUSTER_SIZE", raising=False)
    monkeypatch.setenv("NEXUS_DB_PATH", str(tmp_path / "store" / "n.db"))

    with (
        patch("nexus_distributed_core.start_web_server"),
        patch("nexus_distributed_core.threading.Thread"),
    ):
        core = NexusDistributedCore("NODE-A", 8081, 9091, "MASTER")

    assert core.cluster_mode == MODE_UNCONFIGURED
    assert core.majority is None
    assert core._local_write_block_reason() == "cluster_mode_unconfigured"
    assert core.runtime_health()["healthy"] is True


# ----------------------------------------------------------------------
# Requirement 3: explicit single mode never enables distributed sync
# ----------------------------------------------------------------------


def test_single_mode_writes_locally(capsys):
    core = core_from_env({"NEXUS_CLUSTER_MODE": "single"})

    run_intake(core, ["payload"])

    assert core.persistence.calls == ["append_transaction"]
    assert "BLOQUEADA" not in capsys.readouterr().out


def test_single_mode_listing_only_itself_still_writes():
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "single"},
        peers={"NODE-A": {"node_id": "NODE-A", "role": "MASTER"}},
    )

    run_intake(core, ["payload"])

    assert core.persistence.calls == ["append_transaction"]


def test_single_mode_blocks_sync_from_peer_without_network():
    core = core_from_env({"NEXUS_CLUSTER_MODE": "single"})

    with patch(
        "nexus_distributed_core.socket.create_connection"
    ) as connect:
        with pytest.raises(RuntimeError, match="quorum commit"):
            core.sync_from_peer(PEER)

    connect.assert_not_called()
    assert core.persistence.calls == []


def test_single_mode_blocks_sync_handlers():
    core = core_from_env({"NEXUS_CLUSTER_MODE": "single"})
    conn = RecordingConnection()

    with pytest.raises(RuntimeError, match="quorum commit"):
        core.handle_sync_batch(conn, {"blocks": [{"forged": True}]})

    with pytest.raises(RuntimeError, match="quorum commit"):
        core.handle_state_summary(conn, {"payload": {"height": 0}})

    assert conn.sent == []
    assert core.persistence.calls == []


def test_single_mode_tcp_router_serves_no_blocks():
    core = core_from_env({"NEXUS_CLUSTER_MODE": "single"})
    conn = RecordingConnection(
        {"type": "STATE_SUMMARY", "payload": {"height": 0}}
    )

    core.handle_client(conn)  # logs the block, never raises

    assert conn.sent == []
    assert conn.closed is True
    assert core.persistence.calls == []


# ----------------------------------------------------------------------
# Requirement 4: distributed mode keeps writes blocked
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "env",
    [
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "3"},
        {"NEXUS_CLUSTER_SIZE": "3"},  # legacy launch scripts
    ],
)
def test_distributed_mode_blocks_writes(env, capsys):
    core = core_from_env(env)

    run_intake(core, ["payload-1", "payload-2"])

    assert core.persistence.calls == []
    out = capsys.readouterr().out
    assert out.count("Escrita BLOQUEADA") == 2
    assert "quorum_commit_not_implemented" in out
    assert "NEXUS_CLUSTER_SIZE=3" in out


# ----------------------------------------------------------------------
# Requirement 5: hub peer visibility is never proof of quorum
# ----------------------------------------------------------------------


def test_full_hub_view_does_not_authorize_distributed_writes():
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "3"},
        peers=full_hub_view(with_dead_master=False),
    )

    run_intake(core, ["payload"])

    assert core.persistence.calls == []


def test_full_hub_view_does_not_authorize_unconfigured_writes():
    core = core_from_env({}, peers=full_hub_view(with_dead_master=False))

    run_intake(core, ["payload"])

    assert core.persistence.calls == []


def test_hub_promotion_in_distributed_mode_grants_no_write_authority(
    capsys,
):
    """A hub-visibility promotion is a role label, not commit authority."""
    store = RecordingPersistence()
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "3"},
        role="FOLLOWER",
        persistence=store,
    )

    run_polling(core, full_hub_view())

    assert core.role == "MASTER"  # pre-existing failover behavior

    # run_polling stubs the intake loop; restore the real write gate.
    del core.shell_intake_loop
    run_intake(core, ["payload"])

    assert store.calls == []
    assert "quorum_commit_not_implemented" in capsys.readouterr().out


def test_single_mode_peer_conflict_blocks_writes(capsys):
    """Other members on the hub can only restrict a single node."""
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "single"},
        peers={"NODE-B": {"node_id": "NODE-B", "role": "FOLLOWER"}},
    )

    run_intake(core, ["payload"])

    assert core.persistence.calls == []
    assert "single_mode_peer_conflict" in capsys.readouterr().out


@pytest.mark.parametrize("hub_view", [[], ["NODE-B"], "NODE-B", 3])
def test_single_mode_non_dict_hub_view_blocks_writes(hub_view, capsys):
    core = core_from_env({"NEXUS_CLUSTER_MODE": "single"})
    core.peers = hub_view

    run_intake(core, ["payload"])

    assert core.persistence.calls == []
    assert "single_mode_hub_view_invalid" in capsys.readouterr().out


def test_single_mode_peer_conflict_blocks_promotion(caplog):
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "single"},
        role="FOLLOWER",
    )

    with caplog.at_level("WARNING", logger="nexus.core"):
        run_polling(core, full_hub_view())

    assert core.role == "FOLLOWER"
    assert_promotion_gate_fired(caplog)


def test_single_mode_alone_may_promote():
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "single"},
        role="FOLLOWER",
    )

    run_polling(core, {})

    assert core.role == "MASTER"


# ----------------------------------------------------------------------
# Requirement 6: QS-C01 is not weakened
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"NEXUS_CLUSTER_SIZE": "1"},
        {"NEXUS_CLUSTER_MODE": "single"},
        {"NEXUS_CLUSTER_SIZE": "3"},
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "5"},
    ],
)
def test_legacy_sync_disabled_for_every_valid_configuration(env):
    assert core_from_env(env)._distributed_sync_enabled() is False


@pytest.mark.parametrize(
    "mode,size",
    [
        ("single", 3),
        ("single", None),
        ("single", "1"),
        ("bogus", 1),
    ],
)
def test_tampered_runtime_fields_fail_closed(mode, size):
    """Hand-edited attributes cannot open the write path."""
    core = core_from_env({})
    core.cluster_mode = mode
    core.configured_cluster_size = size

    run_intake(core, ["payload"])

    assert core.persistence.calls == []


def test_bare_core_without_cluster_fields_fails_closed():
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NODE-A"
    core.role = "MASTER"
    core.persistence = RecordingPersistence()

    assert core._distributed_sync_enabled() is False
    assert core._local_write_block_reason() == "cluster_mode_unconfigured"

    run_intake(core, ["payload"])

    assert core.persistence.calls == []


# ----------------------------------------------------------------------
# Requirement 7: existing data stays readable and unchanged
# ----------------------------------------------------------------------


def _digest_dir(path: Path):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.iterdir())
        if p.is_file()
    }


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"NEXUS_CLUSTER_SIZE": "1"},
        {"NEXUS_CLUSTER_SIZE": "3"},
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "3"},
    ],
)
def test_blocked_modes_preserve_and_read_existing_data(tmp_path, env):
    store_dir = tmp_path / "store"
    seed = NexusPersistence(filepath=str(store_dir / "nexus.db"))
    seed.append_transaction({"event": "BEFORE", "n": 1})
    seed.append_transaction({"event": "BEFORE", "n": 2})
    before = _digest_dir(store_dir)

    # Reopen the store as a restarted node would.
    store = NexusPersistence(filepath=str(store_dir / "nexus.db"))
    core = core_from_env(env, persistence=store)

    assert core.runtime_health()["storage"]["height"] == 2
    assert store.recover_state() == {
        "active_workers": {},
        "completed_jobs": [],
        "pending_jobs": [],
    }

    run_intake(core, ["must-not-persist"])
    with pytest.raises(RuntimeError):
        core.handle_sync_batch(None, {"blocks": [{"forged": True}]})

    assert _digest_dir(store_dir) == before
    assert store.validate_chain()


def test_single_mode_appends_to_existing_chain(tmp_path):
    store_dir = tmp_path / "store"
    seed = NexusPersistence(filepath=str(store_dir / "nexus.db"))
    seed.append_transaction({"event": "BEFORE"})

    store = NexusPersistence(filepath=str(store_dir / "nexus.db"))
    core = core_from_env(
        {"NEXUS_CLUSTER_MODE": "single"},
        persistence=store,
    )

    run_intake(core, ["after"])

    assert store.validate_chain()
    assert store.state_summary()["height"] == 2


# ----------------------------------------------------------------------
# Requirement 8: distributed consensus is not enabled
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "env",
    [
        {"NEXUS_CLUSTER_SIZE": "3"},
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "3"},
        {"NEXUS_CLUSTER_MODE": "distributed", "NEXUS_CLUSTER_SIZE": "7"},
    ],
)
def test_no_configuration_enables_distributed_commit(env):
    core = core_from_env(env, peers=full_hub_view(with_dead_master=False))

    assert core._local_write_block_reason() == (
        "quorum_commit_not_implemented"
    )
    assert core._distributed_sync_enabled() is False


def test_environment_is_not_mutated_by_resolution():
    snapshot = dict(os.environ)
    resolve_cluster_mode(os.environ)
    assert dict(os.environ) == snapshot
