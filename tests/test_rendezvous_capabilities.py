from __future__ import annotations

import pytest

from nexus_protocol import NexusProtocol, ReplayCache
from nexus_rendezvous import (
    register_peer,
    update_peer_heartbeat,
)


def make_registration(protocol):
    return protocol.create_envelope(
        sender="NO-ARM-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-ARM-01",
            "role": "FOLLOWER",
            "web_port": 8082,
            "tcp_port": 9092,
            "protocol_version": 1,
            "capabilities": {
                "handlers": [
                    "data_transform",
                    "echo",
                    "matrix_multiply",
                ],
            },
        },
        timestamp=1000.0,
        nonce="cap-register-nonce",
        message_id="cap-register-message",
    )


def make_heartbeat(protocol):
    return protocol.create_envelope(
        sender="NO-ARM-01",
        message_type="HEARTBEAT",
        payload={
            "role": "FOLLOWER",
            "capabilities": {
                "handlers": [
                    "echo",
                    "matrix_multiply",
                ],
            },
        },
        timestamp=1002.0,
        nonce="cap-heartbeat-nonce",
        message_id="cap-heartbeat-message",
    )


def test_registration_stores_node_capabilities():
    protocol = NexusProtocol("test-secret")
    peers = {}

    record = register_peer(
        envelope=make_registration(protocol),
        client_ip="192.168.1.20",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    assert record["capabilities"] == {
        "handlers": [
            "data_transform",
            "echo",
            "matrix_multiply",
        ],
    }

    assert peers["NO-ARM-01"]["capabilities"] == record["capabilities"]


def test_heartbeat_updates_node_capabilities():
    protocol = NexusProtocol("test-secret")
    peers = {}

    register_peer(
        envelope=make_registration(protocol),
        client_ip="192.168.1.20",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    record = update_peer_heartbeat(
        envelope=make_heartbeat(protocol),
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1003.0,
        ttl=60.0,
    )

    assert record["capabilities"] == {
        "handlers": [
            "echo",
            "matrix_multiply",
        ],
    }


def test_registration_defaults_missing_capabilities_to_empty_handlers():
    protocol = NexusProtocol("test-secret")
    peers = {}

    envelope = protocol.create_envelope(
        sender="NO-LEGACY-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-LEGACY-01",
            "role": "FOLLOWER",
            "web_port": 8083,
            "tcp_port": 9093,
            "protocol_version": 1,
        },
        timestamp=1000.0,
        nonce="legacy-register-nonce",
        message_id="legacy-register-message",
    )

    record = register_peer(
        envelope=envelope,
        client_ip="192.168.1.21",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    assert record["capabilities"] == {
        "handlers": [],
    }


def test_registration_preserves_hardware_capabilities():
    protocol = NexusProtocol("test-secret")
    peers = {}

    envelope = protocol.create_envelope(
        sender="NO-HW-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-HW-01",
            "role": "FOLLOWER",
            "web_port": 8084,
            "tcp_port": 9094,
            "protocol_version": 1,
            "capabilities": {
                "handlers": [
                    "echo",
                    "matrix_multiply",
                ],
                "compute_type": "cpu",
                "memory_mb": 16384,
                "has_gpu": False,
            },
        },
        timestamp=1000.0,
        nonce="hardware-register-nonce",
        message_id="hardware-register-message",
    )

    record = register_peer(
        envelope=envelope,
        client_ip="192.168.1.30",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    assert record["capabilities"] == {
        "handlers": [
            "echo",
            "matrix_multiply",
        ],
        "compute_type": "cpu",
        "memory_mb": 16384,
        "has_gpu": False,
    }


def test_heartbeat_updates_hardware_capabilities():
    protocol = NexusProtocol("test-secret")
    peers = {}

    register_envelope = protocol.create_envelope(
        sender="NO-HW-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-HW-01",
            "role": "FOLLOWER",
            "web_port": 8084,
            "tcp_port": 9094,
            "protocol_version": 1,
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": 8192,
                "has_gpu": False,
            },
        },
        timestamp=1000.0,
        nonce="hardware-register-nonce-2",
        message_id="hardware-register-message-2",
    )

    register_peer(
        envelope=register_envelope,
        client_ip="192.168.1.30",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    heartbeat = protocol.create_envelope(
        sender="NO-HW-01",
        message_type="HEARTBEAT",
        payload={
            "role": "FOLLOWER",
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": 16384,
                "has_gpu": False,
            },
        },
        timestamp=1002.0,
        nonce="hardware-heartbeat-nonce",
        message_id="hardware-heartbeat-message",
    )

    record = update_peer_heartbeat(
        envelope=heartbeat,
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1003.0,
        ttl=60.0,
    )

    assert record["capabilities"]["memory_mb"] == 16384
    assert record["capabilities"]["compute_type"] == "cpu"
    assert record["capabilities"]["has_gpu"] is False


def test_registration_rejects_negative_hardware_memory():
    protocol = NexusProtocol("test-secret")
    peers = {}

    envelope = protocol.create_envelope(
        sender="NO-HW-BAD",
        message_type="REGISTER",
        payload={
            "node_id": "NO-HW-BAD",
            "role": "FOLLOWER",
            "web_port": 8085,
            "tcp_port": 9095,
            "protocol_version": 1,
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": -1,
                "has_gpu": False,
            },
        },
        timestamp=1000.0,
        nonce="bad-hardware-register-nonce",
        message_id="bad-hardware-register-message",
    )

    with pytest.raises(
        ValueError,
        match="memory",
    ):
        register_peer(
            envelope=envelope,
            client_ip="192.168.1.31",
            protocol=protocol,
            replay_cache=ReplayCache(),
            peers=peers,
            now=1001.0,
            ttl=60.0,
        )


def test_heartbeat_stores_node_load():
    protocol = NexusProtocol("test-secret")
    peers = {}

    registration = protocol.create_envelope(
        sender="NO-LOAD-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-LOAD-01",
            "role": "FOLLOWER",
            "web_port": 8086,
            "tcp_port": 9096,
            "protocol_version": 1,
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": 8192,
                "has_gpu": False,
            },
        },
        timestamp=1000.0,
        nonce="load-register-nonce",
        message_id="load-register-message",
    )

    register_peer(
        envelope=registration,
        client_ip="192.168.1.40",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    heartbeat = protocol.create_envelope(
        sender="NO-LOAD-01",
        message_type="HEARTBEAT",
        payload={
            "role": "FOLLOWER",
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": 8192,
                "has_gpu": False,
            },
            "load": {
                "active_tasks": 2,
                "queued_tasks": 1,
                "completed_tasks": 10,
                "failed_tasks": 1,
                "average_duration_ms": 12.5,
            },
        },
        timestamp=1002.0,
        nonce="load-heartbeat-nonce",
        message_id="load-heartbeat-message",
    )

    record = update_peer_heartbeat(
        envelope=heartbeat,
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1003.0,
        ttl=60.0,
    )

    assert record["load"] == {
        "active_tasks": 2,
        "queued_tasks": 1,
        "completed_tasks": 10,
        "failed_tasks": 1,
        "average_duration_ms": 12.5,
    }


def test_heartbeat_rejects_negative_node_load():
    protocol = NexusProtocol("test-secret")
    peers = {}

    registration = protocol.create_envelope(
        sender="NO-LOAD-BAD",
        message_type="REGISTER",
        payload={
            "node_id": "NO-LOAD-BAD",
            "role": "FOLLOWER",
            "web_port": 8087,
            "tcp_port": 9097,
            "protocol_version": 1,
        },
        timestamp=1000.0,
        nonce="bad-load-register-nonce",
        message_id="bad-load-register-message",
    )

    register_peer(
        envelope=registration,
        client_ip="192.168.1.41",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    heartbeat = protocol.create_envelope(
        sender="NO-LOAD-BAD",
        message_type="HEARTBEAT",
        payload={
            "role": "FOLLOWER",
            "load": {
                "active_tasks": -1,
                "queued_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "average_duration_ms": 0.0,
            },
        },
        timestamp=1002.0,
        nonce="bad-load-heartbeat-nonce",
        message_id="bad-load-heartbeat-message",
    )

    with pytest.raises(
        ValueError,
        match="load",
    ):
        update_peer_heartbeat(
            envelope=heartbeat,
            protocol=protocol,
            replay_cache=ReplayCache(),
            peers=peers,
            now=1003.0,
            ttl=60.0,
        )


def test_legacy_heartbeat_without_load_remains_supported():
    protocol = NexusProtocol("test-secret")
    peers = {}

    registration = protocol.create_envelope(
        sender="NO-LEGACY-LOAD",
        message_type="REGISTER",
        payload={
            "node_id": "NO-LEGACY-LOAD",
            "role": "FOLLOWER",
            "web_port": 8088,
            "tcp_port": 9098,
            "protocol_version": 1,
        },
        timestamp=1000.0,
        nonce="legacy-load-register-nonce",
        message_id="legacy-load-register-message",
    )

    register_peer(
        envelope=registration,
        client_ip="192.168.1.42",
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    heartbeat = protocol.create_envelope(
        sender="NO-LEGACY-LOAD",
        message_type="HEARTBEAT",
        payload={
            "role": "FOLLOWER",
        },
        timestamp=1002.0,
        nonce="legacy-load-heartbeat-nonce",
        message_id="legacy-load-heartbeat-message",
    )

    record = update_peer_heartbeat(
        envelope=heartbeat,
        protocol=protocol,
        replay_cache=ReplayCache(),
        peers=peers,
        now=1003.0,
        ttl=60.0,
    )

    assert "load" not in record
