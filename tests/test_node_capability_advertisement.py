from __future__ import annotations

from nexus_distributed_core import NexusDistributedCore
from nexus_protocol import NexusProtocol


def make_core():
    core = NexusDistributedCore.__new__(NexusDistributedCore)
    core.node_id = "NO-ARM-01"
    core.role = "FOLLOWER"
    core.web_port = 8082
    core.tcp_port = 9092
    core.protocol = NexusProtocol("test-secret")

    from nexus.compute.handlers import build_default_task_registry
    core.compute_task_handlers = build_default_task_registry()

    return core


def test_node_advertises_registered_compute_handlers():
    core = make_core()

    capabilities = core.compute_capabilities()

    assert capabilities["handlers"] == [
        "data_transform",
        "echo",
        "matrix_multiply",
    ]


def test_registration_envelope_advertises_compute_capabilities():
    core = make_core()

    envelope = core.build_registration_envelope(
        timestamp=1000.0,
        nonce="capability-register-nonce",
        message_id="capability-register-message",
    )

    assert envelope["payload"]["capabilities"] == {
        "handlers": [
            "data_transform",
            "echo",
            "matrix_multiply",
        ],
    }


def test_heartbeat_envelope_advertises_compute_capabilities():
    core = make_core()

    envelope = core.build_heartbeat_envelope(
        timestamp=1000.0,
        nonce="capability-heartbeat-nonce",
        message_id="capability-heartbeat-message",
    )

    assert envelope["payload"]["capabilities"] == {
        "handlers": [
            "data_transform",
            "echo",
            "matrix_multiply",
        ],
    }
