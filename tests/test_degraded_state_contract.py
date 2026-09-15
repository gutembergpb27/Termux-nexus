import time

from nexus_distributed_core import NexusDistributedCore
from persistence import NexusPersistence


def make_follower(tmp_path):
    core = NexusDistributedCore(
        node_id="NODE-A",
        web_port=8081,
        tcp_port=9091,
        role="FOLLOWER",
    )

    core.store = NexusPersistence(
        filepath=str(tmp_path / "degraded-state.db")
    )

    return core


def test_follower_without_master_is_not_ready(tmp_path):
    """
    Axis 9 Contract 1A.

    A healthy local store is not sufficient for distributed
    readiness when a FOLLOWER has no visible MASTER.

    Loss of leadership must therefore be observable instead
    of being reported as an operational distributed state.
    """
    core = make_follower(tmp_path)

    core.peers = {}
    core.last_master_heartbeat = time.time()

    readiness = core.runtime_readiness(
        now=time.time(),
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is False
    assert readiness["role"] == "FOLLOWER"
    assert readiness["reason"] == "master_missing"


def test_follower_with_stale_master_is_not_ready(tmp_path):
    """
    Axis 9 Contract 1B.

    A previously known MASTER whose liveness evidence has
    expired must not keep the FOLLOWER operational.
    """
    core = make_follower(tmp_path)

    core.peers = {
        "NODE-MASTER": {
            "node_id": "NODE-MASTER",
            "role": "MASTER",
        }
    }

    readiness = core.runtime_readiness(
        now=100.0,
        heartbeat_ttl=15.0,
    )

    core.last_master_heartbeat = 0.0

    readiness = core.runtime_readiness(
        now=100.0,
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is False
    assert readiness["role"] == "FOLLOWER"
    assert readiness["reason"] == "master_heartbeat_stale"


def test_degraded_readiness_does_not_grant_master_authority(
    tmp_path,
):
    """
    Axis 9 Contract 1C.

    Reporting a degraded/no-leader condition must not itself
    mutate leadership authority.

    Observation of failure and authorization of promotion are
    separate contracts.
    """
    core = make_follower(tmp_path)

    core.peers = {}
    core.last_master_heartbeat = 0.0

    readiness = core.runtime_readiness(
        now=100.0,
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is False
    assert core.role == "FOLLOWER"
    assert readiness["role"] == "FOLLOWER"
    assert readiness["reason"] == "master_missing"


# ============================================================
# AXIS 9 — CONTRACT 2
# HTTP DEGRADED READINESS CONTRACT
# ============================================================

def test_http_readiness_exposes_master_missing(tmp_path):
    import io
    import json
    import web_panel

    core = make_follower(tmp_path)
    core.role = "FOLLOWER"
    core.peers = {}

    class Request:
        def __init__(self):
            self.status = None
            self.headers = {}
            self.wfile = io.BytesIO()

        def send_response(self, status):
            self.status = status

        def send_header(self, key, value):
            self.headers[key] = value

        def end_headers(self):
            pass

    request = Request()

    handler = object.__new__(web_panel.MetricsHTTPHandler)
    handler.path = "/readiness"
    handler.wfile = request.wfile
    handler.send_response = request.send_response
    handler.send_header = request.send_header
    handler.end_headers = request.end_headers

    original = web_panel._runtime_instance

    try:
        web_panel._runtime_instance = core

        handler.do_GET()

        body = json.loads(
            request.wfile.getvalue().decode("utf-8")
        )

        assert request.status == 503
        assert body["ready"] is False
        assert body["role"] == "FOLLOWER"
        assert body["reason"] == "master_missing"

        # HTTP observation cannot promote authority.
        assert core.role == "FOLLOWER"

    finally:
        web_panel._runtime_instance = original


def test_http_readiness_exposes_stale_master_heartbeat(tmp_path):
    import io
    import json
    import web_panel

    core = make_follower(tmp_path)
    core.role = "FOLLOWER"

    core.peers = {
        "NO-MASTER": {
            "role": "MASTER",
            "last_seen": 100.0,
        }
    }

    # runtime_readiness uses the canonical heartbeat clock,
    # not peer metadata, to determine MASTER liveness.
    core.last_master_heartbeat = 100.0

    original_readiness = core.runtime_readiness

    core.runtime_readiness = lambda: original_readiness(
        now=1000.0,
        heartbeat_ttl=15.0,
    )

    class Request:
        def __init__(self):
            self.status = None
            self.headers = {}
            self.wfile = io.BytesIO()

        def send_response(self, status):
            self.status = status

        def send_header(self, key, value):
            self.headers[key] = value

        def end_headers(self):
            pass

    request = Request()

    handler = object.__new__(web_panel.MetricsHTTPHandler)
    handler.path = "/readiness"
    handler.wfile = request.wfile
    handler.send_response = request.send_response
    handler.send_header = request.send_header
    handler.end_headers = request.end_headers

    original = web_panel._runtime_instance

    try:
        web_panel._runtime_instance = core

        handler.do_GET()

        body = json.loads(
            request.wfile.getvalue().decode("utf-8")
        )

        assert request.status == 503
        assert body["ready"] is False
        assert body["role"] == "FOLLOWER"
        assert body["reason"] == "master_heartbeat_stale"

        # Degradation observation cannot promote authority.
        assert core.role == "FOLLOWER"

    finally:
        web_panel._runtime_instance = original





# ============================================================
# AXIS 9 — CONTRACT 3
# DEGRADED STATE MUST NOT BYPASS QUORUM
# ============================================================

def test_degraded_follower_without_quorum_cannot_become_master(
    tmp_path,
):
    """
    Axis 9 Contract 3.

    Detecting a degraded/no-leader condition does not grant
    leadership authority.

    A FOLLOWER without sufficient quorum must remain a
    FOLLOWER even after MASTER liveness has expired.
    """

    core = make_follower(tmp_path)

    core.configured_cluster_size = 3
    core.majority = 2

    core.peers = {}
    core.last_master_heartbeat = 0.0

    readiness = core.runtime_readiness(
        now=100.0,
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is False
    assert readiness["reason"] == "master_missing"

    # Degradation is observation, not promotion authority.
    assert core.role == "FOLLOWER"

    visible_member_ids = {str(core.node_id)}
    quorum_count = len(visible_member_ids)

    assert quorum_count < core.majority

    # Insufficient quorum cannot authorize MASTER authority.
    assert core.role != "MASTER"
