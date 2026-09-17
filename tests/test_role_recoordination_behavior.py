import io
import json
from unittest.mock import patch

import pytest

from nexus_distributed_core import NexusDistributedCore


class FakeResponse:
    def __init__(self, payload):
        self.status = 200
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class StopPolling(BaseException):
    pass


def make_core(role="MASTER", node_id="NODE-A"):
    core = object.__new__(NexusDistributedCore)

    core.role = role
    core.node_id = node_id
    core.hub_url = "http://127.0.0.1:8500"
    core.peers = {}
    core.last_master_heartbeat = 0.0

    return core


def run_one_polling_iteration(core, peers, post_results):
    calls = []
    sync_calls = []

    def post_envelope(path, envelope):
        calls.append(
            (
                path,
                envelope.get("role"),
            )
        )

        if path == "/register":
            return True

        if not post_results:
            return True

        return post_results.pop(0)

    def registration():
        return {
            "node_id": core.node_id,
            "role": core.role,
        }

    def heartbeat():
        return {
            "node_id": core.node_id,
            "role": core.role,
        }

    def sync(peer):
        sync_calls.append(peer)

    core.post_envelope = post_envelope
    core.build_registration_envelope = registration
    core.build_heartbeat_envelope = heartbeat
    core.sync_from_peer = sync
    core.shell_intake_loop = lambda: None

    sleep_count = 0

    def fake_sleep(_seconds):
        nonlocal sleep_count
        sleep_count += 1

        # First sleep is the normal 5-second polling delay.
        # Any later sleep means the next iteration began.
        if sleep_count > 1:
            raise StopPolling()

    with (
        patch(
            "nexus_distributed_core.time.sleep",
            side_effect=fake_sleep,
        ),
        patch(
            "nexus_distributed_core.time.time",
            return_value=100.0,
        ),
        patch(
            "nexus_distributed_core.urllib.request.urlopen",
            return_value=FakeResponse(peers),
        ),
    ):
        with pytest.raises(StopPolling):
            core.async_polling_loop()

    return calls, sync_calls


def test_demotion_heartbeat_uses_new_follower_role():
    core = make_core(
        role="MASTER",
        node_id="NODE-A",
    )

    peers = {
        "NODE-A": {
            "node_id": "NODE-A",
            "role": "MASTER",
        },
        "NODE-Z": {
            "node_id": "NODE-Z",
            "role": "MASTER",
        },
    }

    calls, sync_calls = run_one_polling_iteration(
        core,
        peers,
        post_results=[
            True,   # initial heartbeat
            True,   # corrective heartbeat
        ],
    )

    assert core.role == "FOLLOWER"

    heartbeat_calls = [
        call for call in calls
        if call[0] == "/heartbeat"
    ]

    assert heartbeat_calls == [
        ("/heartbeat", "MASTER"),
        ("/heartbeat", "FOLLOWER"),
    ]

    assert len(sync_calls) == 1


def test_failed_corrective_heartbeat_keeps_local_demotion():
    core = make_core(
        role="MASTER",
        node_id="NODE-A",
    )

    peers = {
        "NODE-A": {
            "node_id": "NODE-A",
            "role": "MASTER",
        },
        "NODE-Z": {
            "node_id": "NODE-Z",
            "role": "MASTER",
        },
    }

    calls, sync_calls = run_one_polling_iteration(
        core,
        peers,
        post_results=[
            True,    # initial heartbeat
            False,   # corrective heartbeat fails
        ],
    )

    # Demotion is a local safety decision and must not be
    # rolled back merely because Hub acknowledgement failed.
    assert core.role == "FOLLOWER"

    heartbeat_calls = [
        call for call in calls
        if call[0] == "/heartbeat"
    ]

    assert heartbeat_calls == [
        ("/heartbeat", "MASTER"),
        ("/heartbeat", "FOLLOWER"),
    ]

    # Failed corrective publication aborts this iteration.
    assert sync_calls == []


def test_remote_master_refreshes_timeout_after_demotion():
    core = make_core(
        role="MASTER",
        node_id="NODE-A",
    )

    peers = {
        "NODE-A": {
            "node_id": "NODE-A",
            "role": "MASTER",
        },
        "NODE-Z": {
            "node_id": "NODE-Z",
            "role": "MASTER",
        },
    }

    run_one_polling_iteration(
        core,
        peers,
        post_results=[
            True,
            True,
        ],
    )

    assert core.role == "FOLLOWER"
    assert core.last_master_heartbeat == 100.0


def test_existing_remote_master_does_not_trigger_promotion():
    core = make_core(
        role="FOLLOWER",
        node_id="NODE-A",
    )

    # Deliberately stale. Presence of a live MASTER in the
    # current Hub snapshot must refresh it before promotion.
    core.last_master_heartbeat = 0.0

    peers = {
        "NODE-A": {
            "node_id": "NODE-A",
            "role": "FOLLOWER",
        },
        "NODE-Z": {
            "node_id": "NODE-Z",
            "role": "MASTER",
        },
    }

    calls, sync_calls = run_one_polling_iteration(
        core,
        peers,
        post_results=[
            True,
        ],
    )

    assert core.role == "FOLLOWER"
    assert core.last_master_heartbeat == 100.0
    assert len(sync_calls) == 1


def test_lower_id_remote_master_does_not_demote_local_master():
    core = make_core(
        role="MASTER",
        node_id="NODE-Z",
    )

    peers = {
        "NODE-A": {
            "node_id": "NODE-A",
            "role": "MASTER",
        },
        "NODE-Z": {
            "node_id": "NODE-Z",
            "role": "MASTER",
        },
    }

    calls, sync_calls = run_one_polling_iteration(
        core,
        peers,
        post_results=[
            True,
        ],
    )

    assert core.role == "MASTER"

    heartbeat_calls = [
        call for call in calls
        if call[0] == "/heartbeat"
    ]

    # No corrective heartbeat: local node won deterministic
    # tie-break and remains MASTER.
    assert heartbeat_calls == [
        ("/heartbeat", "MASTER"),
    ]

    # A local MASTER must not synchronize from losing MASTER.
    assert sync_calls == []
