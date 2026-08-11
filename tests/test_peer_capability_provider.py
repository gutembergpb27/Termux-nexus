from __future__ import annotations

from nexus.compute.peer_capabilities import PeerCapabilityProvider


def test_provider_returns_known_peer_capabilities() -> None:
    peers = {
        "node-a": {
            "capabilities": {
                "handlers": [
                    "echo",
                    "matrix_multiply",
                ],
            },
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    assert provider("node-a") == {
        "handlers": [
            "echo",
            "matrix_multiply",
        ],
    }


def test_provider_defaults_legacy_peer_to_empty_handlers() -> None:
    peers = {
        "node-a": {
            "role": "FOLLOWER",
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    assert provider("node-a") == {
        "handlers": [],
    }


def test_provider_defaults_unknown_peer_to_empty_handlers() -> None:
    provider = PeerCapabilityProvider(
        lambda: {},
    )

    assert provider("missing") == {
        "handlers": [],
    }


def test_provider_returns_isolated_snapshot() -> None:
    peers = {
        "node-a": {
            "capabilities": {
                "handlers": ["echo"],
            },
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    capabilities = provider("node-a")
    capabilities["handlers"].append("tampered")

    assert peers["node-a"]["capabilities"] == {
        "handlers": ["echo"],
    }
