"""Testes do cliente HTTP reutilizável."""

from __future__ import annotations

import io
import json

import pytest

from nexus.client import NexusClient
from nexus.exceptions import NexusClientError


def test_get_json_returns_dictionary(monkeypatch):
    payload = {"status": "OPERATIONAL"}

    class FakeResponse:
        def __enter__(self):
            return io.StringIO(json.dumps(payload))

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    client = NexusClient()

    assert client.get_json("http://example/status") == payload


def test_get_json_rejects_non_dictionary(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return io.StringIO(json.dumps(["invalid"]))

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    client = NexusClient()

    with pytest.raises(NexusClientError):
        client.get_json("http://example/status")


def test_health_uses_get_json(monkeypatch):
    payload = {"healthy": True}
    requested_urls = []

    client = NexusClient()

    monkeypatch.setattr(
        client,
        "get_json",
        lambda url: requested_urls.append(url) or payload,
    )

    result = client.health("http://example/health")

    assert result == payload
    assert requested_urls == ["http://example/health"]


def test_cluster_uses_get_json(monkeypatch):
    payload = {
        "leader": "NO-WIN-A",
        "followers": ["NO-WIN-B"],
        "nodes": 2,
    }
    requested_urls = []

    client = NexusClient()

    monkeypatch.setattr(
        client,
        "get_json",
        lambda url: requested_urls.append(url) or payload,
    )

    result = client.cluster("http://example/cluster")

    assert result == payload
    assert requested_urls == ["http://example/cluster"]
