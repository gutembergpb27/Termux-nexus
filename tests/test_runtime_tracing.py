from nexus.runtime import Runtime, RuntimeTracing


def test_runtime_tracing_initially_empty():
    tracing = RuntimeTracing()

    assert tracing.count() == 0
    assert tracing.history() == []


def test_runtime_tracing_begin():
    tracing = RuntimeTracing()

    trace = tracing.begin("runtime.test", node="NO-WIN-A")

    assert trace["operation"] == "runtime.test"
    assert trace["status"] == "RUNNING"
    assert trace["context"] == {"node": "NO-WIN-A"}
    assert trace["trace_id"]
    assert tracing.count() == 1


def test_runtime_tracing_finish():
    tracing = RuntimeTracing()

    trace = tracing.begin("runtime.test")

    assert tracing.finish(trace["trace_id"]) is True

    history = tracing.history()

    assert history[0]["status"] == "FINISHED"
    assert history[0]["finished_at"] is not None


def test_runtime_tracing_finish_unknown():
    tracing = RuntimeTracing()

    assert tracing.finish("invalid-trace-id") is False


def test_runtime_tracing_clear():
    tracing = RuntimeTracing()

    tracing.begin("runtime.test")
    tracing.clear()

    assert tracing.count() == 0
    assert tracing.history() == []


def test_runtime_start_generates_trace():
    runtime = Runtime()

    runtime.start()

    traces = runtime.tracing.history()

    assert traces[0]["operation"] == "runtime.start"
    assert traces[0]["status"] == "FINISHED"


def test_runtime_stop_generates_trace():
    runtime = Runtime()

    runtime.start()
    runtime.stop()

    traces = runtime.tracing.history()

    assert traces[-1]["operation"] == "runtime.stop"
    assert traces[-1]["status"] == "FINISHED"


def test_runtime_restart_generates_trace():
    runtime = Runtime()

    runtime.restart()

    operations = [trace["operation"] for trace in runtime.tracing.history()]

    assert "runtime.restart" in operations
