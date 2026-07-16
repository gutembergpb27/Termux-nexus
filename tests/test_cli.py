"""Testes da CLI oficial do Nexus."""

from __future__ import annotations

import io
import json

from nexus.cli import main


def test_version_command(capsys):
    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "Nexus Runtime Platform v2300.0.0-dev"


def test_status_command(monkeypatch, capsys):
    payload = {
        "status": "OPERATIONAL",
        "node_id": "NO-TEST",
        "role": "MASTER",
        "height": 6,
        "term": 0,
    }

    class FakeResponse:
        def __enter__(self):
            return io.StringIO(json.dumps(payload))

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    exit_code = main(["status"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Node: NO-TEST" in captured.out
    assert "Role: MASTER" in captured.out
    assert "Status: OPERATIONAL" in captured.out
    assert "Height: 6" in captured.out
    assert "Term: 0" in captured.out
