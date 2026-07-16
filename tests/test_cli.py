"""Testes da CLI oficial do Nexus."""

from __future__ import annotations

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

    monkeypatch.setattr(
        "nexus.commands.status.NexusClient.status",
        lambda self, url: payload,
    )

    exit_code = main(["status"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Node: NO-TEST" in captured.out
    assert "Role: MASTER" in captured.out
    assert "Status: OPERATIONAL" in captured.out
    assert "Height: 6" in captured.out
    assert "Term: 0" in captured.out


def test_peers_command(monkeypatch, capsys):
    payload = {
        "NO-WIN-A": {
            "role": "MASTER",
            "ip": "192.168.1.7",
            "web_port": 8081,
            "tcp_port": 9091,
        },
        "NO-TERMUX": {
            "role": "FOLLOWER",
            "ip": "192.168.1.8",
            "web_port": 8083,
            "tcp_port": 9093,
        },
    }

    monkeypatch.setattr(
        "nexus.commands.peers.NexusClient.get_json",
        lambda self, url: payload,
    )

    exit_code = main(["peers"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "NO-WIN-A: role=MASTER" in captured.out
    assert "NO-TERMUX: role=FOLLOWER" in captured.out

def test_status_command_json(monkeypatch, capsys):
    payload = {
        "status": "OPERATIONAL",
        "node_id": "NO-TEST",
        "role": "MASTER",
        "height": 6,
        "term": 0,
    }

    monkeypatch.setattr(
        "nexus.commands.status.NexusClient.status",
        lambda self, url: payload,
    )

    exit_code = main(["status", "--json"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        '{"height": 6, "node_id": "NO-TEST", "role": "MASTER", '
        '"status": "OPERATIONAL", "term": 0}'
    )
