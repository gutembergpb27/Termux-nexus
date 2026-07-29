from nexus.runtime import Runtime


def test_runtime_events_initially_empty():
    runtime = Runtime()

    assert runtime.events.count() == 0
    assert runtime.events.history() == []


def test_runtime_events_publish():
    runtime = Runtime()

    event = runtime.events.publish("runtime.test", value=123)

    assert event["event"] == "runtime.test"
    assert event["payload"]["value"] == 123
    assert runtime.events.count() == 1


def test_runtime_events_clear():
    runtime = Runtime()

    runtime.events.publish("runtime.test")
    runtime.events.clear()

    assert runtime.events.count() == 0
    assert runtime.events.history() == []


def test_runtime_start_generates_event():
    runtime = Runtime()

    runtime.start()

    history = runtime.events.history()

    assert history[-1]["event"] == "runtime.started"


def test_runtime_stop_generates_events():
    runtime = Runtime()

    runtime.start()
    runtime.stop()

    history = runtime.events.history()

    assert history[-2]["event"] == "runtime.stopping"
    assert history[-1]["event"] == "runtime.stopped"
