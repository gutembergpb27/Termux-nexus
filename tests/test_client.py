"""Testes do cliente HTTP reutiliz?vel."""

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
