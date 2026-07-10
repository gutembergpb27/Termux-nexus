import copy

import pytest

from nexus_protocol import NexusProtocol, ProtocolError, ReplayCache


def make_protocol():
    return NexusProtocol(secret_key="test-secret")


def make_envelope(protocol, payload=None):
    return protocol.create_envelope(
        sender="NO-ARM-01",
        message_type="HEARTBEAT",
        payload=payload or {"status": "ALIVE"},
        timestamp=1000.0,
        nonce="nonce-001",
        message_id="message-001",
    )


def test_canonical_serialization_produces_stable_signature():
    protocol = make_protocol()

    first = make_envelope(protocol, {"a": 1, "b": 2})
    second = make_envelope(protocol, {"b": 2, "a": 1})

    assert first["signature"] == second["signature"]


def test_accepts_valid_envelope():
    protocol = make_protocol()
    envelope = make_envelope(protocol)

    assert protocol.verify_envelope(
        envelope,
        now=1001.0,
        ttl=60.0,
        replay_cache=ReplayCache(),
    )


def test_rejects_tampered_payload():
    protocol = make_protocol()
    envelope = make_envelope(protocol)

    tampered = copy.deepcopy(envelope)
    tampered["payload"]["status"] = "COMPROMISED"

    with pytest.raises(ProtocolError, match="signature"):
        protocol.verify_envelope(
            tampered,
            now=1001.0,
            ttl=60.0,
            replay_cache=ReplayCache(),
        )


def test_rejects_expired_envelope():
    protocol = make_protocol()
    envelope = make_envelope(protocol)

    with pytest.raises(ProtocolError, match="expired"):
        protocol.verify_envelope(
            envelope,
            now=1100.0,
            ttl=60.0,
            replay_cache=ReplayCache(),
        )


def test_rejects_replayed_message():
    protocol = make_protocol()
    envelope = make_envelope(protocol)
    replay_cache = ReplayCache()

    assert protocol.verify_envelope(
        envelope,
        now=1001.0,
        ttl=60.0,
        replay_cache=replay_cache,
    )

    with pytest.raises(ProtocolError, match="replay"):
        protocol.verify_envelope(
            envelope,
            now=1002.0,
            ttl=60.0,
            replay_cache=replay_cache,
        )
