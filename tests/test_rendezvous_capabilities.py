from __future__ import annotations

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
