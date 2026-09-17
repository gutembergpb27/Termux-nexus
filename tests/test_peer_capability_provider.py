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


def test_provider_preserves_hardware_capabilities() -> None:
    peers = {
        "node-a": {
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
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    assert provider("node-a") == {
        "handlers": [
            "echo",
            "matrix_multiply",
        ],
        "compute_type": "cpu",
        "memory_mb": 16384,
        "has_gpu": False,
    }


def test_provider_preserves_unknown_memory() -> None:
    peers = {
        "node-a": {
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": None,
                "has_gpu": False,
            },
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    assert provider("node-a")["memory_mb"] is None


def test_provider_returns_isolated_hardware_snapshot() -> None:
    peers = {
        "node-a": {
            "capabilities": {
                "handlers": ["echo"],
                "compute_type": "cpu",
                "memory_mb": 8192,
                "has_gpu": False,
            },
        },
    }

    provider = PeerCapabilityProvider(
        lambda: peers,
    )

    capabilities = provider("node-a")

    capabilities["handlers"].append(
        "matrix_multiply"
    )
    capabilities["memory_mb"] = 1

    assert peers["node-a"]["capabilities"] == {
        "handlers": ["echo"],
        "compute_type": "cpu",
        "memory_mb": 8192,
        "has_gpu": False,
    }
