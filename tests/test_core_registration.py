from nexus_distributed_core import NexusDistributedCore
from nexus_protocol import NexusProtocol, ReplayCache


def make_core():
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NO-ARM-01"
    core.web_port = 8082
    core.tcp_port = 9092
    core.role = "FOLLOWER"
    core.protocol = NexusProtocol("test-secret")
    return core


def test_core_builds_authenticated_register_envelope():
    core = make_core()

    envelope = core.build_registration_envelope(
        timestamp=1000.0,
        nonce="core-register-nonce",
        message_id="core-register-message",
    )

    assert envelope["type"] == "REGISTER"
    assert envelope["sender"] == "NO-ARM-01"
    assert envelope["payload"] == {
        "node_id": "NO-ARM-01",
        "role": "FOLLOWER",
        "web_port": 8082,
        "tcp_port": 9092,
        "protocol_version": 1,
    }

    verifier = NexusProtocol("test-secret")
    assert verifier.verify_envelope(
        envelope,
        now=1001.0,
        ttl=60.0,
        replay_cache=ReplayCache(),
    )


def test_registration_reflects_current_role_without_changing_identity():
    core = make_core()
    core.role = "MASTER"

    envelope = core.build_registration_envelope(
        timestamp=1000.0,
        nonce="core-master-nonce",
        message_id="core-master-message",
    )

    assert envelope["sender"] == "NO-ARM-01"
    assert envelope["payload"]["node_id"] == "NO-ARM-01"
    assert envelope["payload"]["role"] == "MASTER"


def test_core_builds_authenticated_heartbeat_envelope():
    core = make_core()

    envelope = core.build_heartbeat_envelope(
        timestamp=1000.0,
        nonce="core-heartbeat-nonce",
        message_id="core-heartbeat-message",
    )

    assert envelope["type"] == "HEARTBEAT"
    assert envelope["sender"] == "NO-ARM-01"
    assert envelope["payload"] == {"role": "FOLLOWER"}

    verifier = NexusProtocol("test-secret")
    assert verifier.verify_envelope(
        envelope,
        now=1001.0,
        ttl=60.0,
        replay_cache=ReplayCache(),
    )


def test_core_builds_authenticated_state_summary_envelope(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "nexus.db")
    )
    core.persistence.append_transaction(
        {"event": "TEST", "data": {"value": 1}}
    )

    envelope = core.build_state_summary_envelope(
        term=7,
        timestamp=1000.0,
        nonce="core-summary-nonce",
        message_id="core-summary-message",
    )

    assert envelope["type"] == "STATE_SUMMARY"
    assert envelope["sender"] == "NO-ARM-01"
    assert envelope["payload"]["height"] == 1
    assert envelope["payload"]["tip_hash"] == core.persistence.last_hash
    assert envelope["payload"]["term"] == 7

    verifier = NexusProtocol("test-secret")
    assert verifier.verify_envelope(
        envelope,
        now=1001.0,
        ttl=60.0,
        replay_cache=ReplayCache(),
    )


def test_runtime_health_reports_valid_storage(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "healthy.db")
    )
    core.term = 4

    health = core.runtime_health()

    assert health["healthy"] is True
    assert health["node_id"] == "NO-ARM-01"
    assert health["role"] == "FOLLOWER"
    assert health["storage"]["valid"] is True
    assert health["storage"]["height"] == 0


def test_runtime_health_reports_storage_failure():
    core = make_core()

    class BrokenPersistence:
        def validate_chain(self):
            raise ValueError("checkpoint mismatch")

    core.persistence = BrokenPersistence()

    health = core.runtime_health()

    assert health["healthy"] is False
    assert health["storage"]["valid"] is False
    assert health["reason"] == "checkpoint mismatch"


def test_runtime_readiness_accepts_healthy_master(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.role = "MASTER"
    core.peers = {}
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "master.db")
    )

    readiness = core.runtime_readiness(now=1000.0)

    assert readiness["ready"] is True
    assert readiness["reason"] == "master_operational"


def test_runtime_readiness_accepts_follower_with_recent_master(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.peers = {
        "NO-MASTER-01": {
            "node_id": "NO-MASTER-01",
            "role": "MASTER",
        },
    }
    core.last_master_heartbeat = 995.0
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "follower.db")
    )

    readiness = core.runtime_readiness(
        now=1000.0,
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is True
    assert readiness["reason"] == "follower_operational"
    assert readiness["leader"] == "NO-MASTER-01"
    assert readiness["master_heartbeat_age"] == 5.0


def test_runtime_readiness_rejects_follower_without_master(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.peers = {}
    core.last_master_heartbeat = 1000.0
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "missing-master.db")
    )

    readiness = core.runtime_readiness(now=1000.0)

    assert readiness["ready"] is False
    assert readiness["reason"] == "master_missing"


def test_runtime_readiness_rejects_stale_master_heartbeat(tmp_path):
    from persistence import NexusPersistence

    core = make_core()
    core.peers = {
        "NO-MASTER-01": {
            "node_id": "NO-MASTER-01",
            "role": "MASTER",
        },
    }
    core.last_master_heartbeat = 970.0
    core.persistence = NexusPersistence(
        filepath=str(tmp_path / "stale-master.db")
    )

    readiness = core.runtime_readiness(
        now=1000.0,
        heartbeat_ttl=15.0,
    )

    assert readiness["ready"] is False
    assert readiness["reason"] == "master_heartbeat_stale"


def test_runtime_readiness_rejects_unhealthy_storage():
    core = make_core()
    core.peers = {}

    core.runtime_health = lambda: {
        "healthy": False,
        "reason": "checkpoint mismatch",
    }

    readiness = core.runtime_readiness(now=1000.0)

    assert readiness["ready"] is False
    assert readiness["reason"] == "storage_unhealthy"
