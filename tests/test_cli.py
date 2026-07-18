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


def test_peers_command_json(monkeypatch, capsys):
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

    exit_code = main(["peers", "--json"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        '{"NO-TERMUX": {"ip": "192.168.1.8", '
        '"role": "FOLLOWER", "tcp_port": 9093, '
        '"web_port": 8083}, '
        '"NO-WIN-A": {"ip": "192.168.1.7", '
        '"role": "MASTER", "tcp_port": 9091, '
        '"web_port": 8081}}'
    )

def test_cluster_command_json(monkeypatch, capsys):
    payload = {
        "status": "OPERATIONAL",
        "leader": "NO-WIN-A",
        "nodes": 2,
        "followers": ["NO-WIN-B"],
    }

    monkeypatch.setattr(
        "nexus.commands.cluster.NexusClient.get_json",
        lambda self, url: payload,
    )

    exit_code = main(["cluster", "--json"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        '{"followers": ["NO-WIN-B"], '
        '"leader": "NO-WIN-A", '
        '"nodes": 2, '
        '"status": "OPERATIONAL"}'
    )


def test_doctor_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "nexus.commands.doctor.collect_diagnostics",
        lambda: {
            "checks": {
                "python": {
                    "status": "OK",
                    "version": "3.14.6",
                },
                "working_directory": {
                    "path": r"C:\Termux-nexus",
                    "status": "OK",
                    "writable": True,
                },
            },
            "executable": r"C:\Python314\python.exe",
            "platform": "Windows-Test",
            "python": "3.14.6",
            "status": "OK",
            "version": "2300.0.0-dev",
            "working_dir": r"C:\Termux-nexus",
        },
    )

    exit_code = main(["doctor"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Nexus Runtime Platform Doctor" in captured.out
    assert "CLI Version : 2300.0.0-dev" in captured.out
    assert "Python      : 3.14.6" in captured.out
    assert "Platform    : Windows-Test" in captured.out
    assert "Executable  : C:\\Python314\\python.exe" in captured.out
    assert "Working Dir : C:\\Termux-nexus" in captured.out
    assert "[ OK ] Python 3.14.6" in captured.out
    assert "[ OK ] Working directory writable: True" in captured.out
    assert "Status: OK" in captured.out


def test_doctor_command_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "nexus.commands.doctor.collect_diagnostics",
        lambda: {
            "checks": {
                "python": {
                    "status": "OK",
                    "version": "3.14.6",
                },
                "working_directory": {
                    "path": r"C:\Termux-nexus",
                    "status": "OK",
                    "writable": True,
                },
            },
            "executable": r"C:\Python314\python.exe",
            "platform": "Windows-Test",
            "python": "3.14.6",
            "status": "OK",
            "version": "2300.0.0-dev",
            "working_dir": r"C:\Termux-nexus",
        },
    )

    exit_code = main(["doctor", "--json"])

    captured = capsys.readouterr()

    assert exit_code == 0

    payload = __import__("json").loads(captured.out)

    assert payload["status"] == "OK"
    assert payload["version"] == "2300.0.0-dev"
    assert payload["checks"]["python"]["status"] == "OK"
    assert payload["checks"]["working_directory"]["writable"] is True


def test_doctor_returns_error_when_directory_is_not_writable(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "nexus.commands.doctor.collect_diagnostics",
        lambda: {
            "checks": {
                "python": {
                    "status": "OK",
                    "version": "3.14.6",
                },
                "working_directory": {
                    "path": r"C:\ReadOnly",
                    "status": "ERROR",
                    "writable": False,
                },
            },
            "executable": r"C:\Python314\python.exe",
            "platform": "Windows-Test",
            "python": "3.14.6",
            "status": "ERROR",
            "version": "2300.0.0-dev",
            "working_dir": r"C:\ReadOnly",
        },
    )

    exit_code = main(["doctor"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "[ERROR] Working directory writable: False" in captured.out
    assert "Status: ERROR" in captured.out
