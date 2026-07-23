"""Testes da CLI oficial do Nexus."""

from __future__ import annotations

from nexus import __version__
from nexus.cli import main


def test_version_command(capsys):
    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == f"Nexus Runtime Platform v{__version__}"


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
            "version": __version__,
            "working_dir": r"C:\Termux-nexus",
        },
    )

    exit_code = main(["doctor"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Nexus Runtime Platform Doctor" in captured.out
    assert f"CLI Version : {__version__}" in captured.out
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
            "version": __version__,
            "working_dir": r"C:\Termux-nexus",
        },
    )

    exit_code = main(["doctor", "--json"])

    captured = capsys.readouterr()

    assert exit_code == 0

    payload = __import__("json").loads(captured.out)

    assert payload["status"] == "OK"
    assert payload["version"] == __version__
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
            "version": __version__,
            "working_dir": r"C:\ReadOnly",
        },
    )

    exit_code = main(["doctor"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "[ERROR] Working directory writable: False" in captured.out
    assert "Status: ERROR" in captured.out


def test_doctor_reports_runtime_identity(monkeypatch, capsys):
    payload = {
        "status": "OPERATIONAL",
        "node_id": "NO-TEST",
        "role": "MASTER",
        "height": 6,
        "term": 0,
    }

    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.status",
        lambda self, url: payload,
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.health",
        lambda self, url: {"healthy": True},
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.cluster",
        lambda self, url: {
            "leader": "NO-TEST",
            "followers": [],
            "nodes": 1,
        },
    )

    exit_code = main(
        [
            "doctor",
            "--url",
            "http://127.0.0.1:8081/status",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Runtime:" in captured.out
    assert "[ OK ] Node ID: NO-TEST" in captured.out
    assert "[ OK ] Role: MASTER" in captured.out
    assert "[ OK ] Runtime status: OPERATIONAL" in captured.out
    assert "[ OK ] Height: 6" in captured.out
    assert "[ OK ] Term: 0" in captured.out



def test_doctor_reports_health_and_cluster(monkeypatch, capsys):
    requested_urls = []

    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.status",
        lambda self, url: requested_urls.append(url) or {
            "status": "OPERATIONAL",
            "node_id": "NO-TEST",
            "role": "MASTER",
            "height": 6,
            "term": 1,
        },
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.health",
        lambda self, url: requested_urls.append(url) or {
            "healthy": True,
            "storage": {
                "valid": True,
            },
        },
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.NexusClient.cluster",
        lambda self, url: requested_urls.append(url) or {
            "leader": "NO-TEST",
            "followers": ["NO-FOLLOWER"],
            "nodes": 2,
        },
    )

    exit_code = main(
        [
            "doctor",
            "--url",
            "http://127.0.0.1:8081/status",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert requested_urls == [
        "http://127.0.0.1:8081/status",
        "http://127.0.0.1:8081/health",
        "http://127.0.0.1:8081/cluster",
    ]
    assert "Health:" in captured.out
    assert "[ OK ] Healthy: True" in captured.out
    assert "[ OK ] Storage valid: True" in captured.out
    assert "Cluster:" in captured.out
    assert "[ OK ] Leader: NO-TEST" in captured.out
    assert "[ OK ] Followers: NO-FOLLOWER" in captured.out
    assert "[ OK ] Nodes: 2" in captured.out


def test_doctor_watch_runs_repeatedly(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "nexus.commands.doctor.run_once",
        lambda args: calls.append(args.url) or 0,
        raising=False,
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.time.sleep",
        lambda interval: (_ for _ in ()).throw(KeyboardInterrupt),
        raising=False,
    )

    exit_code = main(
        [
            "doctor",
            "--url",
            "http://127.0.0.1:8081/status",
            "--watch",
        ]
    )

    assert exit_code == 0
    assert calls == ["http://127.0.0.1:8081/status"]


def test_doctor_watch_uses_custom_interval(monkeypatch):
    calls = []
    intervals = []

    monkeypatch.setattr(
        "nexus.commands.doctor.run_once",
        lambda args: calls.append(args.url) or 0,
    )

    def fake_sleep(interval):
        intervals.append(interval)
        raise KeyboardInterrupt

    monkeypatch.setattr(
        "nexus.commands.doctor.time.sleep",
        fake_sleep,
    )

    exit_code = main(
        [
            "doctor",
            "--url",
            "http://127.0.0.1:8081/status",
            "--watch",
            "--interval",
            "2.5",
        ]
    )

    assert exit_code == 0
    assert calls == ["http://127.0.0.1:8081/status"]
    assert intervals == [2.5]


def test_doctor_watch_clear_screen_before_refresh(monkeypatch):
    events = []

    monkeypatch.setattr(
        "nexus.commands.doctor.clear_screen",
        lambda: events.append("clear"),
        raising=False,
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.run_once",
        lambda args: events.append("run") or 0,
    )
    monkeypatch.setattr(
        "nexus.commands.doctor.time.sleep",
        lambda interval: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    exit_code = main(
        [
            "doctor",
            "--watch",
            "--clear",
        ]
    )

    assert exit_code == 0
    assert events == ["clear", "run"]
