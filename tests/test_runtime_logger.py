from nexus.runtime import Runtime, RuntimeLogger


def test_runtime_logger_initially_empty():
    logger = RuntimeLogger()

    assert logger.count() == 0
    assert logger.history() == []


def test_runtime_logger_records_structured_entry():
    logger = RuntimeLogger()

    record = logger.info("Runtime ready", node="NO-WIN-A")

    assert record["level"] == "INFO"
    assert record["message"] == "Runtime ready"
    assert record["context"] == {"node": "NO-WIN-A"}
    assert isinstance(record["timestamp"], str)
    assert logger.count() == 1


def test_runtime_logger_supports_all_levels():
    logger = RuntimeLogger()

    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
    logger.critical("critical")

    levels = [record["level"] for record in logger.history()]

    assert levels == [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]


def test_runtime_logger_clear():
    logger = RuntimeLogger()

    logger.info("Runtime ready")
    logger.clear()

    assert logger.count() == 0
    assert logger.history() == []


def test_runtime_start_generates_logs():
    runtime = Runtime()

    runtime.start()

    messages = [record["message"] for record in runtime.logger.history()]

    assert messages == [
        "Runtime starting",
        "Runtime started",
    ]


def test_runtime_stop_generates_logs():
    runtime = Runtime()

    runtime.start()
    runtime.stop()

    messages = [record["message"] for record in runtime.logger.history()]

    assert messages[-2:] == [
        "Runtime stopping",
        "Runtime stopped",
    ]


def test_runtime_restart_generates_request_log():
    runtime = Runtime()

    runtime.restart()

    messages = [record["message"] for record in runtime.logger.history()]

    assert messages[0] == "Runtime restart requested"
