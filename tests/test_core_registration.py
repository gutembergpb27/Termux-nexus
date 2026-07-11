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
