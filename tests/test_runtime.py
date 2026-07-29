"""Tests for the Nexus Runtime API."""

from nexus import Runtime
from nexus.runtime.state import RuntimeState


def test_runtime_starts_stopped() -> None:
    runtime = Runtime()
    assert runtime.started is False


def test_runtime_start() -> None:
    runtime = Runtime()
    runtime.start()
    assert runtime.started is True


def test_runtime_stop() -> None:
    runtime = Runtime()
    runtime.start()
    runtime.stop()
    assert runtime.started is False


def test_runtime_initial_state() -> None:
    runtime = Runtime()
    assert runtime.state is RuntimeState.STOPPED


def test_runtime_restart() -> None:
    runtime = Runtime()
    runtime.restart()
    assert runtime.started is True
    assert runtime.state is RuntimeState.RUNNING


def test_runtime_status() -> None:
    runtime = Runtime()

    status = runtime.status()

    assert status["started"] is False
    assert status["state"] == "stopped"

    runtime.start()

    status = runtime.status()

    assert status["started"] is True
    assert status["state"] == "running"


def test_runtime_health_check() -> None:
    runtime = Runtime()

    report = runtime.health.check()

    assert report["healthy"] is False
    assert report["runtime"]["state"] == "stopped"
    assert "python" in report
    assert "platform" in report
    assert "version" in report


def test_runtime_health_summary() -> None:
    runtime = Runtime()
    runtime.start()

    summary = runtime.health.summary()

    assert summary["healthy"] is True
    assert summary["state"] == "running"