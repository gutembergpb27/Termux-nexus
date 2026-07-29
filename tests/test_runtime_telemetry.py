from nexus.runtime import Runtime


def test_telemetry_initial_snapshot():
    runtime = Runtime()

    snapshot = runtime.telemetry.snapshot()

    assert snapshot["runtime"]["started"] is False
    assert snapshot["runtime"]["state"] == "stopped"
    assert snapshot["counters"]["events"] == 0
    assert snapshot["counters"]["logs"] == 0
    assert snapshot["counters"]["traces"] == 0


def test_telemetry_after_start():
    runtime = Runtime()

    runtime.start()

    snapshot = runtime.telemetry.snapshot()

    assert snapshot["runtime"]["started"] is True
    assert snapshot["runtime"]["state"] == "running"
    assert snapshot["counters"]["events"] == 1
    assert snapshot["counters"]["logs"] == 2
    assert snapshot["counters"]["traces"] == 1


def test_telemetry_after_restart():
    runtime = Runtime()

    runtime.start()
    runtime.restart()

    counters = runtime.telemetry.counters()

    assert counters["events"] == 4
    assert counters["logs"] == 7
    assert counters["traces"] == 4


def test_telemetry_counters():
    runtime = Runtime()

    counters = runtime.telemetry.counters()

    assert counters["events"] == 0
    assert counters["logs"] == 0
    assert counters["traces"] == 0
