from nexus.runtime import Runtime


def test_diagnostics_initial_snapshot():
    runtime = Runtime()

    snapshot = runtime.diagnostics.snapshot()

    assert snapshot["runtime"]["started"] is False
    assert snapshot["health"]["healthy"] is False
    assert snapshot["observability"]["events"] == 0
    assert snapshot["observability"]["logs"] == 0
    assert snapshot["observability"]["traces"] == 0
    assert snapshot["observability"]["active_traces"] == 0


def test_diagnostics_after_start():
    runtime = Runtime()

    runtime.start()

    snapshot = runtime.diagnostics.snapshot()

    assert snapshot["runtime"]["started"] is True
    assert snapshot["health"]["healthy"] is True
    assert snapshot["observability"]["events"] == 1
    assert snapshot["observability"]["logs"] == 2
    assert snapshot["observability"]["traces"] == 1
    assert snapshot["observability"]["active_traces"] == 0


def test_diagnostics_after_restart():
    runtime = Runtime()

    runtime.start()
    runtime.restart()

    snapshot = runtime.diagnostics.snapshot()

    assert snapshot["runtime"]["started"] is True
    assert snapshot["observability"]["events"] == 4
    assert snapshot["observability"]["logs"] == 7
    assert snapshot["observability"]["traces"] == 4
    assert snapshot["observability"]["active_traces"] == 0


def test_diagnostics_summary():
    runtime = Runtime()

    runtime.start()

    summary = runtime.diagnostics.summary()

    assert summary["started"] is True
    assert summary["healthy"] is True
    assert summary["events"] == 1
    assert summary["logs"] == 2
    assert summary["traces"] == 1
    assert summary["active_traces"] == 0


def test_axis3_diagnostics_expose_formal_readiness():
    """Axis 3: diagnostics expose authoritative Runtime readiness."""
    from nexus.runtime import Runtime

    runtime = Runtime()

    assert runtime.diagnostics.snapshot()["readiness"] == {
        "ready": False,
        "reason": "runtime_not_started",
    }

    runtime.start()

    try:
        assert runtime.diagnostics.snapshot()["readiness"] == {
            "ready": True,
            "reason": "runtime_operational",
        }
    finally:
        runtime.stop()

    assert runtime.diagnostics.snapshot()["readiness"] == {
        "ready": False,
        "reason": "runtime_not_started",
    }


def test_axis3_diagnostics_summary_exposes_readiness():
    """Axis 3: compact diagnostics include readiness state and reason."""
    from nexus.runtime import Runtime

    runtime = Runtime()

    summary = runtime.diagnostics.summary()

    assert summary["ready"] is False
    assert summary["readiness_reason"] == "runtime_not_started"

    runtime.start()

    try:
        summary = runtime.diagnostics.summary()

        assert summary["ready"] is True
        assert summary["readiness_reason"] == "runtime_operational"
    finally:
        runtime.stop()
