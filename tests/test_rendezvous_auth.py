import copy

import pytest

from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache
from nexus_rendezvous import register_peer


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
        },
        timestamp=1000.0,
        nonce="register-nonce-001",
        message_id="register-message-001",
    )


def test_authenticated_registration_stores_peer():
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

    assert peers["NO-ARM-01"] == record
    assert record["ip"] == "192.168.1.20"
    assert record["role"] == "FOLLOWER"
    assert record["last_seen"] == 1001.0


def test_tampered_registration_is_rejected():
    protocol = NexusProtocol("test-secret")
    peers = {}
    envelope = make_registration(protocol)

    tampered = copy.deepcopy(envelope)
    tampered["payload"]["role"] = "MASTER"

    with pytest.raises(ProtocolError, match="signature"):
        register_peer(
            envelope=tampered,
            client_ip="192.168.1.20",
            protocol=protocol,
            replay_cache=ReplayCache(),
            peers=peers,
            now=1001.0,
            ttl=60.0,
        )

    assert peers == {}


def test_replayed_registration_is_rejected():
    protocol = NexusProtocol("test-secret")
    peers = {}
    replay_cache = ReplayCache()
    envelope = make_registration(protocol)

    register_peer(
        envelope=envelope,
        client_ip="192.168.1.20",
        protocol=protocol,
        replay_cache=replay_cache,
        peers=peers,
        now=1001.0,
        ttl=60.0,
    )

    with pytest.raises(ProtocolError, match="replay"):
        register_peer(
            envelope=envelope,
            client_ip="192.168.1.20",
            protocol=protocol,
            replay_cache=replay_cache,
            peers=peers,
            now=1002.0,
            ttl=60.0,
        )
