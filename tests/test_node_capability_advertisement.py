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
    core.hardware_capabilities = lambda: {
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
    }

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
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
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
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
    }


def test_node_advertises_hardware_capabilities():
    core = make_core()

    core.hardware_capabilities = lambda: {
        "compute_type": "cpu",
        "memory_mb": 16384,
        "has_gpu": False,
    }

    capabilities = core.compute_capabilities()

    assert capabilities == {
        "handlers": [
            "data_transform",
            "echo",
            "matrix_multiply",
        ],
        "compute_type": "cpu",
        "memory_mb": 16384,
        "has_gpu": False,
    }


def test_registration_envelope_advertises_hardware_capabilities():
    core = make_core()

    core.hardware_capabilities = lambda: {
        "compute_type": "cpu",
        "memory_mb": 8192,
        "has_gpu": False,
    }

    envelope = core.build_registration_envelope(
        timestamp=1000.0,
        nonce="hardware-register-nonce",
        message_id="hardware-register-message",
    )

    assert envelope["payload"]["capabilities"]["compute_type"] == "cpu"
    assert envelope["payload"]["capabilities"]["memory_mb"] == 8192
    assert envelope["payload"]["capabilities"]["has_gpu"] is False


def test_heartbeat_envelope_advertises_hardware_capabilities():
    core = make_core()

    core.hardware_capabilities = lambda: {
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
    }

    envelope = core.build_heartbeat_envelope(
        timestamp=1000.0,
        nonce="hardware-heartbeat-nonce",
        message_id="hardware-heartbeat-message",
    )

    assert envelope["payload"]["capabilities"] == {
        "handlers": [
            "data_transform",
            "echo",
            "matrix_multiply",
        ],
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
    }


def test_heartbeat_envelope_advertises_node_load():
    core = make_core()

    core.compute_node_load = lambda: __import__(
        "nexus.compute",
        fromlist=["NodeLoad"],
    ).NodeLoad(
        active_tasks=2,
        queued_tasks=1,
        completed_tasks=10,
        failed_tasks=1,
        average_duration_ms=12.5,
    )

    envelope = core.build_heartbeat_envelope(
        timestamp=1000.0,
        nonce="load-heartbeat-nonce",
        message_id="load-heartbeat-message",
    )

    assert envelope["payload"]["load"] == {
        "active_tasks": 2,
        "queued_tasks": 1,
        "completed_tasks": 10,
        "failed_tasks": 1,
        "average_duration_ms": 12.5,
    }


def test_registration_envelope_does_not_advertise_dynamic_load():
    core = make_core()

    envelope = core.build_registration_envelope(
        timestamp=1000.0,
        nonce="load-register-nonce",
        message_id="load-register-message",
    )

    assert "load" not in envelope["payload"]
