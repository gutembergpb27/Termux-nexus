from __future__ import annotations

from nexus.compute import NodeLoad
from nexus.compute.peer_load import PeerLoadProvider


def test_provider_returns_peer_load() -> None:
    peers = {
        "node-a": {
            "load": {
                "active_tasks": 2,
                "queued_tasks": 1,
                "completed_tasks": 10,
                "failed_tasks": 1,
                "average_duration_ms": 12.5,
            },
        },
    }

    provider = PeerLoadProvider(
        lambda: peers,
    )

    assert provider("node-a") == NodeLoad(
        active_tasks=2,
        queued_tasks=1,
        completed_tasks=10,
        failed_tasks=1,
        average_duration_ms=12.5,
    )


def test_provider_returns_unknown_for_peer_without_load() -> None:
    peers = {
        "node-a": {
            "capabilities": {
                "handlers": ["echo"],
            },
        },
    }

    provider = PeerLoadProvider(
        lambda: peers,
    )

    assert provider("node-a") is None


def test_provider_returns_unknown_peer_as_none() -> None:
    provider = PeerLoadProvider(
        lambda: {},
    )

    assert provider("missing") is None


def test_provider_returns_isolated_snapshot() -> None:
    peers = {
        "node-a": {
            "load": {
                "active_tasks": 1,
                "queued_tasks": 2,
                "completed_tasks": 8,
                "failed_tasks": 0,
                "average_duration_ms": 5.0,
            },
        },
    }

    provider = PeerLoadProvider(
        lambda: peers,
    )

    first = provider("node-a")
    second = provider("node-a")

    assert first == second
    assert first is not second
