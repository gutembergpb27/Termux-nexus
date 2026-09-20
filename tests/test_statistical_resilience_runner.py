from pathlib import Path
import subprocess

import pytest

import importlib.util
import sys


RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "statistical-resilience"
    / "physical_runner.py"
)

SPEC = importlib.util.spec_from_file_location(
    "nexus_axis11_physical_runner",
    RUNNER_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Axis 11 physical runner")

physical_runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = physical_runner
SPEC.loader.exec_module(physical_runner)

DEFAULT_CLUSTER_SIZE = physical_runner.DEFAULT_CLUSTER_SIZE
DEFAULT_NODES = physical_runner.DEFAULT_NODES
RUNNER_SCHEMA = physical_runner.RUNNER_SCHEMA
NodeSpec = physical_runner.NodeSpec
build_environment = physical_runner.build_environment
build_hub_command = physical_runner.build_hub_command
build_node_command = physical_runner.build_node_command
deterministic_candidate = physical_runner.deterministic_candidate
evidence_directory = physical_runner.evidence_directory
initial_evidence = physical_runner.initial_evidence
stop_process = physical_runner.stop_process
validate_topology = physical_runner.validate_topology


def test_default_topology_is_three_node_quorum_topology():
    validate_topology(DEFAULT_NODES)

    assert DEFAULT_CLUSTER_SIZE == 3
    assert [node.node_id for node in DEFAULT_NODES] == [
        "NODE-A",
        "NODE-B",
        "NODE-C",
    ]

    assert [node.role for node in DEFAULT_NODES] == [
        "MASTER",
        "FOLLOWER",
        "FOLLOWER",
    ]


def test_default_candidate_after_node_a_failure_is_node_c():
    assert deterministic_candidate(
        DEFAULT_NODES,
        failed_master_id="NODE-A",
    ) == "NODE-C"


def test_node_command_matches_runtime_cli_contract():
    command = build_node_command(
        "python",
        NodeSpec("NODE-C", 8083, 9093, "FOLLOWER"),
    )

    assert command == [
        "python",
        "nexus_distributed_core.py",
        "NODE-C",
        "8083",
        "9093",
        "FOLLOWER",
    ]


def test_hub_command_matches_runtime_entrypoint():
    assert build_hub_command("python") == [
        "python",
        "nexus_rendezvous.py",
    ]


def test_environment_contains_required_physical_cluster_values():
    env = build_environment(
        secret_key="axis11-test-secret",
        base={"EXISTING": "preserved"},
    )

    assert env["EXISTING"] == "preserved"
    assert env["NEXUS_SECRET_KEY"] == "axis11-test-secret"
    assert env["NEXUS_HUB_URL"] == "http://127.0.0.1:8500"
    assert env["NEXUS_CLUSTER_SIZE"] == "3"


def test_initial_evidence_preserves_full_t0_to_t4_timeline():
    evidence = initial_evidence()

    assert evidence["schema"] == RUNNER_SCHEMA
    assert evidence["classification"] == "pending"
    assert evidence["experiment"] == "three-node-master-loss-failover"

    assert evidence["timeline"] == {
        "t0": None,
        "t1": None,
        "t2": None,
        "t3": None,
        "t4": None,
    }

    assert evidence["promoted_node"] is None
    assert evidence["converged"] is False
    assert evidence["active_split_brain_observed"] is False


def test_evidence_directory_is_run_scoped(tmp_path: Path):
    result = evidence_directory(tmp_path, "run-001")

    assert result == tmp_path / "run-001"


@pytest.mark.parametrize(
    "run_id",
    ["", "   ", "../run", "a/b", r"a\b"],
)
def test_evidence_directory_rejects_unsafe_run_ids(
    tmp_path: Path,
    run_id: str,
):
    with pytest.raises(ValueError):
        evidence_directory(tmp_path, run_id)


def test_topology_rejects_duplicate_node_id():
    nodes = (
        NodeSpec("NODE-A", 8081, 9091, "MASTER"),
        NodeSpec("NODE-A", 8082, 9092, "FOLLOWER"),
        NodeSpec("NODE-C", 8083, 9093, "FOLLOWER"),
    )

    with pytest.raises(ValueError, match="node_id"):
        validate_topology(nodes)


def test_topology_rejects_duplicate_port():
    nodes = (
        NodeSpec("NODE-A", 8081, 9091, "MASTER"),
        NodeSpec("NODE-B", 8081, 9092, "FOLLOWER"),
        NodeSpec("NODE-C", 8083, 9093, "FOLLOWER"),
    )

    with pytest.raises(ValueError, match="ports"):
        validate_topology(nodes)


def test_topology_requires_exactly_one_master():
    nodes = (
        NodeSpec("NODE-A", 8081, 9091, "FOLLOWER"),
        NodeSpec("NODE-B", 8082, 9092, "FOLLOWER"),
        NodeSpec("NODE-C", 8083, 9093, "FOLLOWER"),
    )

    with pytest.raises(ValueError, match="MASTER"):
        validate_topology(nodes)


def test_stop_process_does_nothing_for_finished_process():
    class FinishedProcess:
        def __init__(self):
            self.terminate_called = False

        def poll(self):
            return 0

        def terminate(self):
            self.terminate_called = True

    process = FinishedProcess()

    stop_process(process)

    assert process.terminate_called is False


def test_stop_process_terminates_running_process():
    class RunningProcess:
        def __init__(self):
            self.terminated = False
            self.wait_calls = []

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.wait_calls.append(timeout)
            return 0

    process = RunningProcess()

    stop_process(process, wait_seconds=2.0)

    assert process.terminated is True
    assert process.wait_calls == [2.0]


def test_stop_process_kills_after_terminate_timeout():
    class StubbornProcess:
        def __init__(self):
            self.killed = False
            self.wait_count = 0

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout):
            self.wait_count += 1
            if self.wait_count == 1:
                raise subprocess.TimeoutExpired(
                    cmd="node",
                    timeout=timeout,
                )
            return 0

        def kill(self):
            self.killed = True

    process = StubbornProcess()

    stop_process(process)

    assert process.killed is True
    assert process.wait_count == 2

def test_timeline_complete_t0_to_t4():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=100.000,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )
    recorder.record(
        "t1",
        monotonic_seconds=116.000,
        observed_at_utc="2026-09-18T12:00:16+00:00",
        source="node-log",
    )
    recorder.record(
        "t2",
        monotonic_seconds=116.100,
        observed_at_utc="2026-09-18T12:00:16.100000+00:00",
        source="node-log",
    )
    recorder.record(
        "t3",
        monotonic_seconds=116.150,
        observed_at_utc="2026-09-18T12:00:16.150000+00:00",
        source="node-log",
    )
    recorder.record(
        "t4",
        monotonic_seconds=116.500,
        observed_at_utc="2026-09-18T12:00:16.500000+00:00",
        source="hub",
    )

    assert recorder.complete() is True

    assert recorder.timing_ms() == {
        "t0_to_t1": 16000.0,
        "t1_to_t2": 100.0,
        "t2_to_t3": 50.0,
        "t1_to_t3": 150.0,
        "t3_to_t4": 350.0,
        "t0_to_t4": 16500.0,
    }


def test_timeline_incomplete_run_is_preserved():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=10.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )
    recorder.record(
        "t1",
        monotonic_seconds=26.0,
        observed_at_utc="2026-09-18T12:00:16+00:00",
        source="node-log",
    )

    assert recorder.complete() is False

    evidence = recorder.as_evidence()

    assert evidence["t0"] is not None
    assert evidence["t1"] is not None
    assert evidence["t2"] is None
    assert evidence["t3"] is None
    assert evidence["t4"] is None

    assert recorder.timing_ms() == {
        "t0_to_t1": 16000.0,
    }


def test_timeline_rejects_duplicate_event():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=1.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )

    with pytest.raises(
        ValueError,
        match="already recorded",
    ):
        recorder.record(
            "t0",
            monotonic_seconds=2.0,
            observed_at_utc="2026-09-18T12:00:01+00:00",
            source="runner",
        )


def test_timeline_rejects_monotonic_order_violation():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=100.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )

    with pytest.raises(
        ValueError,
        match="monotonic order",
    ):
        recorder.record(
            "t1",
            monotonic_seconds=99.0,
            observed_at_utc="2026-09-18T12:00:01+00:00",
            source="node-log",
        )


def test_timeline_rejects_unknown_event():
    recorder = physical_runner.TimelineRecorder()

    with pytest.raises(ValueError, match="unknown"):
        recorder.record(
            "t5",
            monotonic_seconds=1.0,
            observed_at_utc="2026-09-18T12:00:00+00:00",
            source="runner",
        )


def test_apply_timeline_updates_evidence_without_mutating_original():
    original = physical_runner.initial_evidence()

    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=1.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )

    updated = physical_runner.apply_timeline(
        original,
        recorder,
    )

    assert original["timeline"]["t0"] is None
    assert updated["timeline"]["t0"]["source"] == "runner"
    assert updated["timing_ms"] == {}

def _complete_recorder():
    recorder = physical_runner.TimelineRecorder()

    values = {
        "t0": 10.0,
        "t1": 26.0,
        "t2": 26.1,
        "t3": 26.2,
        "t4": 26.5,
    }

    for event, value in values.items():
        recorder.record(
            event,
            monotonic_seconds=value,
            observed_at_utc=(
                "2026-09-18T12:00:00+00:00"
            ),
            source="test-observer",
        )

    return recorder


def test_complete_converged_run_is_valid():
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node="NODE-C",
        converged=True,
        active_split_brain_observed=False,
    )

    assert evidence["classification"] == "valid"
    assert evidence["promoted_node"] == "NODE-C"
    assert evidence["converged"] is True
    assert evidence["invalid_reason"] is None


def test_incomplete_run_is_preserved_as_invalid():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=10.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )

    recorder.record(
        "t1",
        monotonic_seconds=26.0,
        observed_at_utc="2026-09-18T12:00:16+00:00",
        source="node-log",
    )

    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        recorder,
        promoted_node=None,
        converged=False,
        active_split_brain_observed=False,
    )

    assert evidence["classification"] == "invalid"
    assert evidence["timeline"]["t0"] is not None
    assert evidence["timeline"]["t1"] is not None
    assert evidence["timeline"]["t2"] is None
    assert "incomplete timeline" in evidence["invalid_reason"]


def test_split_brain_forces_invalid_classification():
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node="NODE-C",
        converged=True,
        active_split_brain_observed=True,
    )

    assert evidence["classification"] == "invalid"
    assert "split-brain" in evidence["invalid_reason"]


def test_missing_external_convergence_is_invalid():
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node="NODE-C",
        converged=False,
        active_split_brain_observed=False,
    )

    assert evidence["classification"] == "invalid"
    assert "convergence" in evidence["invalid_reason"]


def test_missing_promoted_node_is_invalid():
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node=None,
        converged=True,
        active_split_brain_observed=False,
    )

    assert evidence["classification"] == "invalid"
    assert "promoted node" in evidence["invalid_reason"]


def test_explicit_invalid_reason_is_preserved():
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node="NODE-C",
        converged=True,
        active_split_brain_observed=False,
        invalid_reason="observer integrity failure",
    )

    assert evidence["classification"] == "invalid"
    assert evidence["invalid_reason"] == (
        "observer integrity failure"
    )


def test_save_evidence_json_is_deterministic_utf8_lf(tmp_path):
    evidence = physical_runner.classify_run(
        physical_runner.initial_evidence(),
        _complete_recorder(),
        promoted_node="NODE-C",
        converged=True,
        active_split_brain_observed=False,
    )

    path = tmp_path / "run-001" / "benchmark-summary.json"

    result = physical_runner.save_evidence_json(
        path,
        evidence,
    )

    assert result == path
    assert path.exists()

    raw = path.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")

    first = raw
    physical_runner.save_evidence_json(path, evidence)
    second = path.read_bytes()

    assert first == second

def test_hub_observer_detects_converged_node_c():
    peers = {
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    state = physical_runner.observe_hub_state(
        peers,
        failed_master_id="NODE-A",
    )

    assert state["failed_master_present"] is False
    assert state["masters"] == ["NODE-C"]
    assert state["master_count"] == 1
    assert state["surviving_count"] == 2
    assert state["promoted_node"] == "NODE-C"
    assert state["active_split_brain"] is False

    assert physical_runner.convergence_from_hub_state(
        state
    ) is True


def test_hub_observer_detects_active_split_brain():
    peers = {
        "NODE-B": {"role": "MASTER"},
        "NODE-C": {"role": "MASTER"},
    }

    state = physical_runner.observe_hub_state(
        peers,
        failed_master_id="NODE-A",
    )

    assert state["master_count"] == 2
    assert state["active_split_brain"] is True
    assert state["promoted_node"] is None

    assert physical_runner.convergence_from_hub_state(
        state
    ) is False


def test_old_master_still_present_is_not_converged():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "FOLLOWER"},
    }

    state = physical_runner.observe_hub_state(
        peers,
        failed_master_id="NODE-A",
    )

    assert state["failed_master_present"] is True

    assert physical_runner.convergence_from_hub_state(
        state
    ) is False


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("master_missing", "t1"),
        ("leadership_promotion_started", "t2"),
        ("leadership_promoted", "t3"),
    ],
)
def test_log_observer_maps_runtime_events(marker, expected):
    line = (
        "2026-09-18 INFO node=NODE-C event="
        + marker
    )

    assert physical_runner.observe_log_event(line) == expected


def test_log_observer_ignores_unrelated_lines():
    assert physical_runner.observe_log_event(
        "INFO heartbeat_ok node=NODE-C"
    ) is None


def test_log_observer_rejects_ambiguous_line():
    line = (
        "master_missing "
        "leadership_promotion_started"
    )

    with pytest.raises(ValueError, match="ambiguous"):
        physical_runner.observe_log_event(line)


def test_external_t4_returns_observed_result():
    peers = {
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    converged, promoted, split_brain = (
        physical_runner.observe_external_t4(
            peers,
            failed_master_id="NODE-A",
        )
    )

    assert converged is True
    assert promoted == "NODE-C"
    assert split_brain is False


def test_external_t4_does_not_invent_promotion():
    peers = {
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "FOLLOWER"},
    }

    converged, promoted, split_brain = (
        physical_runner.observe_external_t4(
            peers,
            failed_master_id="NODE-A",
        )
    )

    assert converged is False
    assert promoted is None
    assert split_brain is False

def test_fetch_peers_uses_injected_opener():
    class Response:
        def __init__(self):
            self.closed = False

        def read(self):
            return (
                b'{"NODE-B":{"role":"FOLLOWER"},'
                b'"NODE-C":{"role":"MASTER"}}'
            )

        def close(self):
            self.closed = True

    response = Response()
    calls = []

    def opener(url, timeout):
        calls.append((url, timeout))
        return response

    peers = physical_runner.fetch_peers(
        "http://127.0.0.1:8500/",
        timeout_seconds=1.25,
        opener=opener,
    )

    assert calls == [
        ("http://127.0.0.1:8500/peers", 1.25)
    ]
    assert peers["NODE-C"]["role"] == "MASTER"
    assert response.closed is True


def test_fetch_peers_rejects_non_mapping_payload():
    class Response:
        def read(self):
            return b'["NODE-A"]'

        def close(self):
            pass

    with pytest.raises(ValueError, match="mapping"):
        physical_runner.fetch_peers(
            "http://hub",
            opener=lambda url, timeout: Response(),
        )


def test_incremental_log_reader_returns_only_new_lines(tmp_path):
    path = tmp_path / "node-c.stderr.log"

    path.write_text(
        "first\nsecond\n",
        encoding="utf-8",
    )

    reader = physical_runner.IncrementalLogReader(path)

    assert reader.read_new_lines() == [
        "first",
        "second",
    ]

    with path.open("a", encoding="utf-8") as handle:
        handle.write("third\n")

    assert reader.read_new_lines() == ["third"]
    assert reader.read_new_lines() == []


def test_incremental_log_reader_handles_missing_file(tmp_path):
    reader = physical_runner.IncrementalLogReader(
        tmp_path / "missing.log"
    )

    assert reader.read_new_lines() == []


def test_incremental_log_reader_handles_truncation(tmp_path):
    path = tmp_path / "node.log"
    path.write_text("old-one\nold-two\n", encoding="utf-8")

    reader = physical_runner.IncrementalLogReader(path)

    assert reader.read_new_lines() == [
        "old-one",
        "old-two",
    ]

    path.write_text("new-one\n", encoding="utf-8")

    assert reader.read_new_lines() == ["new-one"]


def test_start_process_uses_injected_factory(tmp_path):
    captured = {}

    class FakeProcess:
        pass

    fake_process = FakeProcess()

    def factory(
        command,
        *,
        env,
        stdin,
        stdout,
        stderr,
        text,
    ):
        captured["command"] = command
        captured["env"] = env
        captured["stdin"] = stdin
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["text"] = text
        return fake_process

    process, stdout_handle, stderr_handle = (
        physical_runner.start_process(
            ["python", "fake.py"],
            environment={"A": "B"},
            stdout_path=tmp_path / "stdout.log",
            stderr_path=tmp_path / "stderr.log",
            popen_factory=factory,
        )
    )

    try:
        assert process is fake_process
        assert captured["command"] == [
            "python",
            "fake.py",
        ]
        assert captured["env"] == {"A": "B"}
        assert captured["stdin"] is subprocess.DEVNULL
        assert captured["text"] is True
        assert stdout_handle.closed is False
        assert stderr_handle.closed is False
    finally:
        physical_runner.close_process_handles(
            stdout_handle,
            stderr_handle,
        )

    assert stdout_handle.closed is True
    assert stderr_handle.closed is True


def test_start_process_closes_handles_when_factory_fails(
    tmp_path,
    monkeypatch,
):
    opened = []

    original_open = Path.open

    def tracked_open(self, *args, **kwargs):
        handle = original_open(self, *args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", tracked_open)

    def failing_factory(*args, **kwargs):
        raise RuntimeError("synthetic launch failure")

    with pytest.raises(
        RuntimeError,
        match="synthetic launch failure",
    ):
        physical_runner.start_process(
            ["python", "fake.py"],
            environment={},
            stdout_path=tmp_path / "stdout.log",
            stderr_path=tmp_path / "stderr.log",
            popen_factory=failing_factory,
        )

    assert len(opened) == 2
    assert all(handle.closed for handle in opened)

class FakeClock:
    def __init__(self, start=100.0):
        self.value = float(start)

    def monotonic(self):
        return self.value

    def utc(self):
        return (
            "2026-09-18T12:00:"
            + f"{self.value - 100.0:06.3f}"
            + "+00:00"
        )

    def sleep(self, seconds):
        self.value += float(seconds)


def test_orchestrator_complete_fake_failover():
    clock = FakeClock()

    terminated = []

    log_batches = iter(
        [
            [],
            [
                "INFO event=master_missing node=NODE-C",
            ],
            [
                "INFO event=leadership_promotion_started "
                "node=NODE-C",
            ],
            [
                "INFO event=leadership_promoted node=NODE-C",
            ],
        ]
    )

    peer_batches = iter(
        [
            {
                "NODE-A": {"role": "MASTER"},
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ]
    )

    def read_logs():
        return next(log_batches, [])

    def read_peers():
        return next(
            peer_batches,
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        )

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: terminated.append(True),
        read_log_lines=read_logs,
        read_peers=read_peers,
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.1,
    )

    assert terminated == [True]
    assert result["classification"] == "valid"
    assert result["promoted_node"] == "NODE-C"
    assert result["converged"] is True
    assert result["active_split_brain_observed"] is False

    assert all(
        result["timeline"][event] is not None
        for event in ("t0", "t1", "t2", "t3", "t4")
    )

    assert result["timing_ms"]["t0_to_t4"] >= 0


def test_orchestrator_timeout_preserves_incomplete_run():
    clock = FakeClock()

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: [],
        read_peers=lambda: {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "FOLLOWER"},
        },
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=0.3,
        poll_interval_seconds=0.1,
    )

    assert result["classification"] == "invalid"
    assert result["timeline"]["t0"] is not None
    assert result["timeline"]["t1"] is None
    assert result["timeline"]["t4"] is None
    assert result["converged"] is False
    assert (
        result["invalid_reason"]
        == "timeout before external convergence"
    )


def test_orchestrator_remembers_transient_split_brain():
    clock = FakeClock()

    logs = iter(
        [
            ["event=master_missing"],
            ["event=leadership_promotion_started"],
            ["event=leadership_promoted"],
        ]
    )

    peers = iter(
        [
            {
                "NODE-B": {"role": "MASTER"},
                "NODE-C": {"role": "MASTER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ]
    )

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: next(logs, []),
        read_peers=lambda: next(
            peers,
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ),
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.1,
    )

    assert result["converged"] is True
    assert result["active_split_brain_observed"] is True
    assert result["classification"] == "invalid"
    assert "split-brain" in result["invalid_reason"]


def test_orchestrator_ignores_out_of_order_t3():
    clock = FakeClock()

    batches = iter(
        [
            ["event=leadership_promoted"],
            ["event=master_missing"],
            ["event=leadership_promotion_started"],
            ["event=leadership_promoted"],
        ]
    )

    peer_calls = {"count": 0}

    def peers():
        peer_calls["count"] += 1

        if peer_calls["count"] < 4:
            return {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            }

        return {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        }

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: next(batches, []),
        read_peers=peers,
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.1,
    )

    assert result["classification"] == "valid"
    assert result["timeline"]["t3"] is not None


def test_orchestrator_rejects_invalid_poll_interval():
    with pytest.raises(ValueError, match="poll_interval"):
        physical_runner.orchestrate_failover(
            evidence=physical_runner.initial_evidence(),
            failed_master_id="NODE-A",
            terminate_master=lambda: None,
            read_log_lines=lambda: [],
            read_peers=lambda: {},
            monotonic_clock=lambda: 1.0,
            utc_clock=lambda: "UTC",
            sleep=lambda seconds: None,
            poll_interval_seconds=0,
        )

def test_physical_run_layout_is_run_scoped(tmp_path):
    layout = physical_runner.PhysicalRunLayout(
        root=tmp_path / "evidence",
        run_id="run-001",
    )

    assert layout.run_directory == (
        tmp_path / "evidence" / "run-001"
    )

    assert layout.logs_directory == (
        tmp_path / "evidence" / "run-001" / "logs"
    )

    assert layout.state_directory == (
        tmp_path / "evidence" / "run-001" / "state"
    )

    assert layout.evidence_path == (
        tmp_path
        / "evidence"
        / "run-001"
        / "benchmark-summary.json"
    )


def test_node_state_paths_are_isolated(tmp_path):
    layout = physical_runner.PhysicalRunLayout(
        root=tmp_path,
        run_id="run-001",
    )

    paths = {
        layout.node_db_path("NODE-A"),
        layout.node_db_path("NODE-B"),
        layout.node_db_path("NODE-C"),
    }

    assert len(paths) == 3

    assert all(
        path.parent == layout.state_directory
        for path in paths
    )


def test_process_logs_are_separated(tmp_path):
    layout = physical_runner.PhysicalRunLayout(
        root=tmp_path,
        run_id="run-001",
    )

    assert (
        layout.stdout_path("hub")
        != layout.stderr_path("hub")
    )

    assert (
        layout.stdout_path("NODE-A")
        != layout.stdout_path("NODE-B")
    )


@pytest.mark.parametrize(
    "unsafe",
    [
        "",
        "../run-001",
        "nested/run",
        r"nested\run",
    ],
)
def test_layout_rejects_unsafe_run_id(tmp_path, unsafe):
    with pytest.raises(ValueError):
        physical_runner.PhysicalRunLayout(
            root=tmp_path,
            run_id=unsafe,
        )


def test_build_physical_environment_preserves_base():
    env = physical_runner.build_physical_environment(
        secret_key="synthetic-test-secret",
        hub_url="http://127.0.0.1:8500",
        cluster_size=3,
        db_path="state/NODE-A.jsonl",
        base_environment={
            "PATH": "synthetic-path",
            "SystemRoot": r"C:\Windows",
            "KEEP_ME": "yes",
        },
    )

    assert env["PATH"] == "synthetic-path"
    assert env["SystemRoot"] == r"C:\Windows"
    assert env["KEEP_ME"] == "yes"
    assert env["NEXUS_CLUSTER_SIZE"] == "3"
    assert env["NEXUS_HUB_URL"] == (
        "http://127.0.0.1:8500"
    )
    assert env["NEXUS_DB_PATH"].endswith(
        "NODE-A.jsonl"
    )


def test_build_physical_environment_uses_os_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_AXIS11_SENTINEL",
        "preserved",
    )

    env = physical_runner.build_physical_environment(
        secret_key="synthetic-test-secret",
        hub_url="http://127.0.0.1:8500",
        cluster_size=3,
    )

    assert env["NEXUS_AXIS11_SENTINEL"] == "preserved"


def test_prepare_run_layout_creates_expected_directories(
    tmp_path,
):
    layout = physical_runner.PhysicalRunLayout(
        root=tmp_path / "evidence",
        run_id="run-001",
    )

    result = physical_runner.prepare_run_layout(layout)

    assert result is layout
    assert layout.run_directory.is_dir()
    assert layout.logs_directory.is_dir()
    assert layout.state_directory.is_dir()


def test_prepare_run_layout_refuses_collision(tmp_path):
    layout = physical_runner.PhysicalRunLayout(
        root=tmp_path / "evidence",
        run_id="run-001",
    )

    physical_runner.prepare_run_layout(layout)

    with pytest.raises(FileExistsError):
        physical_runner.prepare_run_layout(layout)


def test_physical_sleep_rejects_negative_value():
    with pytest.raises(ValueError):
        physical_runner.physical_sleep(-0.001)


def test_physical_monotonic_clock_returns_float():
    value = physical_runner.physical_monotonic_clock()

    assert isinstance(value, float)
    assert value >= 0
def test_timeline_exposes_canonical_t1_to_t3_timing():
    recorder = physical_runner.TimelineRecorder()

    recorder.record(
        "t0",
        monotonic_seconds=10.0,
        observed_at_utc="2026-09-18T12:00:00+00:00",
        source="runner",
    )
    recorder.record(
        "t1",
        monotonic_seconds=20.0,
        observed_at_utc="2026-09-18T12:00:10+00:00",
        source="node-log",
    )
    recorder.record(
        "t2",
        monotonic_seconds=21.0,
        observed_at_utc="2026-09-18T12:00:11+00:00",
        source="node-log",
    )
    recorder.record(
        "t3",
        monotonic_seconds=22.0,
        observed_at_utc="2026-09-18T12:00:12+00:00",
        source="node-log",
    )
    recorder.record(
        "t4",
        monotonic_seconds=23.0,
        observed_at_utc="2026-09-18T12:00:13+00:00",
        source="hub",
    )

    timing = recorder.timing_ms()

    assert timing["t1_to_t3"] == 2000.0
    assert timing["t1_to_t2"] == 1000.0
    assert timing["t2_to_t3"] == 1000.0
    assert timing["t3_to_t4"] == 1000.0
    assert timing["t0_to_t4"] == 13000.0

def test_build_provenance_contains_no_secret():
    provenance = physical_runner.build_provenance(
        run_id="run-001",
        git_sha="abc123",
        python_version="3.14.6",
        platform_description="Windows-test",
        captured_at_utc="2026-09-18T16:30:00+00:00",
    )

    assert provenance["run_id"] == "run-001"
    assert provenance["git_sha"] == "abc123"
    assert provenance["source"] == (
        "measured-physical-runner"
    )
    assert provenance["cluster_size"] == 3
    assert provenance["node_ids"] == [
        "NODE-A",
        "NODE-B",
        "NODE-C",
    ]
    assert provenance["authentication"] == (
        "shared-secret-hmac"
    )
    assert provenance["transport_confidentiality"] is False

    serialized = repr(provenance)

    assert "NEXUS_SECRET_KEY" not in serialized
    assert "secret_key" not in serialized


def test_build_provenance_records_anchor_limitation():
    provenance = physical_runner.build_provenance(
        run_id="run-anchor",
        git_sha="abc123",
        python_version="3.14.6",
        platform_description="Windows-test",
        captured_at_utc="2026-09-18T16:30:00+00:00",
    )

    assert provenance["external_anchor"]["configured"] is False
    assert "does not configure" in (
        provenance["external_anchor"]["reason"]
    )


def test_attach_provenance_does_not_mutate_original():
    evidence = physical_runner.initial_evidence()

    provenance = physical_runner.build_provenance(
        run_id="run-attach",
        git_sha="abc123",
        python_version="3.14.6",
        platform_description="Windows-test",
        captured_at_utc="2026-09-18T16:30:00+00:00",
    )

    result = physical_runner.attach_provenance(
        evidence,
        provenance,
    )

    assert "provenance" not in evidence
    assert result["provenance"] == provenance


def test_cleanup_managed_processes_reverse_order():
    calls = []

    class FakeProcess:
        pass

    class FakeHandle:
        pass

    managed = [
        physical_runner.ManagedProcess(
            "hub",
            FakeProcess(),
            FakeHandle(),
            FakeHandle(),
        ),
        physical_runner.ManagedProcess(
            "NODE-A",
            FakeProcess(),
            FakeHandle(),
            FakeHandle(),
        ),
        physical_runner.ManagedProcess(
            "NODE-B",
            FakeProcess(),
            FakeHandle(),
            FakeHandle(),
        ),
    ]

    process_names = {
        id(item.process): item.process_id
        for item in managed
    }

    def stopper(process):
        calls.append(
            ("stop", process_names[id(process)])
        )

    def closer(stdout_handle, stderr_handle):
        calls.append(
            ("close", id(stdout_handle), id(stderr_handle))
        )

    errors = physical_runner.cleanup_managed_processes(
        managed,
        stopper=stopper,
        handle_closer=closer,
    )

    assert errors == []

    stop_calls = [
        item
        for item in calls
        if item[0] == "stop"
    ]

    assert stop_calls == [
        ("stop", "NODE-B"),
        ("stop", "NODE-A"),
        ("stop", "hub"),
    ]


def test_cleanup_continues_after_stop_failure():
    calls = []

    class FakeProcess:
        pass

    managed = [
        physical_runner.ManagedProcess(
            "hub",
            FakeProcess(),
        ),
        physical_runner.ManagedProcess(
            "NODE-A",
            FakeProcess(),
        ),
    ]

    process_names = {
        id(item.process): item.process_id
        for item in managed
    }

    def stopper(process):
        name = process_names[id(process)]
        calls.append(("stop", name))

        if name == "NODE-A":
            raise RuntimeError("controlled stop failure")

    def closer(*handles):
        calls.append(("close", len(handles)))

    errors = physical_runner.cleanup_managed_processes(
        managed,
        stopper=stopper,
        handle_closer=closer,
    )

    assert ("stop", "NODE-A") in calls
    assert ("stop", "hub") in calls
    assert len(errors) == 1
    assert "NODE-A: stop failed" in errors[0]


def test_lifecycle_cleanup_runs_after_success():
    events = []

    managed = [
        physical_runner.ManagedProcess(
            "fake",
            object(),
        )
    ]

    def body():
        events.append("body")
        return "ok"

    def stopper(process):
        events.append("stop")

    def closer(*handles):
        events.append("close")

    result = physical_runner.lifecycle_with_cleanup(
        body=body,
        managed=managed,
        stopper=stopper,
        handle_closer=closer,
    )

    assert result == "ok"
    assert events == [
        "body",
        "stop",
        "close",
    ]


def test_lifecycle_cleanup_runs_after_exception():
    events = []

    managed = [
        physical_runner.ManagedProcess(
            "fake",
            object(),
        )
    ]

    def body():
        events.append("body")
        raise RuntimeError("controlled body failure")

    def stopper(process):
        events.append("stop")

    def closer(*handles):
        events.append("close")

    with pytest.raises(
        RuntimeError,
        match="controlled body failure",
    ):
        physical_runner.lifecycle_with_cleanup(
            body=body,
            managed=managed,
            stopper=stopper,
            handle_closer=closer,
        )

    assert events == [
        "body",
        "stop",
        "close",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", ""),
        ("git_sha", ""),
        ("python_version", ""),
        ("platform_description", ""),
        ("captured_at_utc", ""),
    ],
)
def test_build_provenance_rejects_empty_identity(
    field,
    value,
):
    kwargs = {
        "run_id": "run-001",
        "git_sha": "abc123",
        "python_version": "3.14.6",
        "platform_description": "Windows-test",
        "captured_at_utc": (
            "2026-09-18T16:30:00+00:00"
        ),
    }

    kwargs[field] = value

    with pytest.raises(ValueError):
        physical_runner.build_provenance(**kwargs)

@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_observation_rejects_non_finite_monotonic(value):
    with pytest.raises(
        ValueError,
        match="monotonic_seconds must be finite",
    ):
        physical_runner.Observation(
            event="t0",
            monotonic_seconds=value,
            observed_at_utc=(
                "2026-09-18T16:30:00+00:00"
            ),
            source="test",
        )


def test_orchestrator_waits_for_t3_before_t4():
    evidence = physical_runner.initial_evidence()

    class FakeClock:
        def __init__(self):
            self.value = 100.0

        def __call__(self):
            self.value += 0.01
            return self.value

        def sleep(self, seconds):
            self.value += seconds

    clock = FakeClock()

    # First poll: Hub is already externally converged, but only
    # T1/T2 are visible. Second poll exposes T3.
    log_batches = iter(
        [
            [
                "master_missing node=NODE-A",
                (
                    "leadership_promotion_started "
                    "node=NODE-C"
                ),
            ],
            [
                "leadership_promoted node=NODE-C",
            ],
        ]
    )

    peer_snapshots = iter(
        [
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ]
    )

    terminated = []

    def terminate_master():
        terminated.append(True)

    def read_log_lines():
        try:
            return next(log_batches)
        except StopIteration:
            return []

    def read_peers():
        try:
            return next(peer_snapshots)
        except StopIteration:
            return {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            }

    result = physical_runner.orchestrate_failover(
        evidence=evidence,
        failed_master_id="NODE-A",
        terminate_master=terminate_master,
        read_log_lines=read_log_lines,
        read_peers=read_peers,
        monotonic_clock=clock,
        utc_clock=lambda: (
            "2026-09-18T16:30:00+00:00"
        ),
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.05,
        expected_survivors=2,
    )

    assert terminated == [True]
    assert result["classification"] == "valid"
    assert result["converged"] is True
    assert result["promoted_node"] == "NODE-C"

    assert result["timeline"]["t3"] is not None
    assert result["timeline"]["t4"] is not None

    assert result["timing_ms"]["t3_to_t4"] >= 0.0


def test_orchestrator_convergence_without_t3_times_out_invalid():
    evidence = physical_runner.initial_evidence()

    class FakeClock:
        def __init__(self):
            self.value = 200.0

        def __call__(self):
            self.value += 0.10
            return self.value

        def sleep(self, seconds):
            self.value += seconds

    clock = FakeClock()

    first = True

    def read_log_lines():
        nonlocal first

        if first:
            first = False
            return [
                "master_missing node=NODE-A",
                (
                    "leadership_promotion_started "
                    "node=NODE-C"
                ),
            ]

        return []

    def read_peers():
        return {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        }

    result = physical_runner.orchestrate_failover(
        evidence=evidence,
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=read_log_lines,
        read_peers=read_peers,
        monotonic_clock=clock,
        utc_clock=lambda: (
            "2026-09-18T16:30:00+00:00"
        ),
        sleep=clock.sleep,
        timeout_seconds=1.0,
        poll_interval_seconds=0.05,
        expected_survivors=2,
    )

    assert result["classification"] == "invalid"
    assert result["converged"] is False
    assert result["timeline"]["t3"] is None
    assert result["timeline"]["t4"] is None
    assert result["invalid_reason"] == (
        "timeout before external convergence"
    )


def test_axis11_incremental_reader_captures_physical_stderr_events(tmp_path):
    log_path = tmp_path / "NODE-C.stderr.log"

    log_path.write_text(
        "2026-09-18 WARNING master_missing node=NODE-C seconds=19.2\n"
        "2026-09-18 INFO leadership_promotion_started node=NODE-C\n"
        "2026-09-18 INFO leadership_promoted node=NODE-C role=MASTER\n",
        encoding="utf-8",
    )

    reader = physical_runner.IncrementalLogReader(log_path)
    lines = reader.read_new_lines()

    assert len(lines) == 3
    assert physical_runner.observe_log_event(lines[0]) == "t1"
    assert physical_runner.observe_log_event(lines[1]) == "t2"
    assert physical_runner.observe_log_event(lines[2]) == "t3"

    assert reader.read_new_lines() == []


def test_axis11_hub_state_preserves_active_split_brain_semantics():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    state = physical_runner.observe_hub_state(
        peers,
        failed_master_id="NODE-A",
    )

    assert state["failed_master_present"] is True
    assert state["masters"] == ["NODE-A", "NODE-C"]
    assert state["master_count"] == 2
    assert state["active_split_brain"] is True

    assert (
        physical_runner.convergence_from_hub_state(
            state,
            expected_survivors=2,
        )
        is False
    )


def test_axis11_hub_state_converges_after_failed_master_expires():
    peers = {
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    state = physical_runner.observe_hub_state(
        peers,
        failed_master_id="NODE-A",
    )

    assert state["failed_master_present"] is False
    assert state["masters"] == ["NODE-C"]
    assert state["surviving_nodes"] == ["NODE-B", "NODE-C"]
    assert state["active_split_brain"] is False
    assert state["promoted_node"] == "NODE-C"

    assert (
        physical_runner.convergence_from_hub_state(
            state,
            expected_survivors=2,
        )
        is True
    )

# ================================================================
# AXIS11_PHASE24F_MASTER_OVERLAP
# ================================================================


def test_phase24f_exact_survivor_set_is_required_when_supplied():
    state = physical_runner.observe_hub_state(
        {
            "NODE-X": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
        failed_master_id="NODE-A",
    )

    assert physical_runner.convergence_from_hub_state(
        state,
        expected_survivors=2,
    ) is True

    assert physical_runner.convergence_from_hub_state(
        state,
        expected_survivors=2,
        expected_survivor_ids={"NODE-B", "NODE-C"},
    ) is False


def test_phase24f_overlap_is_quantified_and_classification_stays_conservative():
    clock = FakeClock()

    logs = iter(
        [
            ["event=master_missing"],
            ["event=leadership_promotion_started"],
            ["event=leadership_promoted"],
            [],
            [],
        ]
    )

    peer_states = iter(
        [
            {
                "NODE-A": {"role": "MASTER"},
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "FOLLOWER"},
            },
            {
                "NODE-A": {"role": "MASTER"},
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
            {
                "NODE-A": {"role": "MASTER"},
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ]
    )

    def read_peers():
        return next(
            peer_states,
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        )

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: next(logs, []),
        read_peers=read_peers,
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.1,
        expected_survivors=2,
        expected_survivor_ids={"NODE-B", "NODE-C"},
    )

    overlap = result["hub_master_overlap"]

    assert result["classification"] == "invalid"
    assert result["converged"] is True
    assert result["active_split_brain_observed"] is True
    assert "split-brain" in result["invalid_reason"]

    assert overlap["multiple_master_records_observed"] is True
    assert ["NODE-A", "NODE-C"] in overlap["master_sets_observed"]
    assert overlap["first_observed_monotonic_seconds"] is not None
    assert overlap["last_observed_monotonic_seconds"] is not None
    assert overlap["duration_ms"] is not None
    assert overlap["duration_ms"] >= 0.0

    assert (
        "does not independently prove"
        in overlap["semantics"]
    )


def test_phase24f_no_overlap_records_zero_overlap_semantics():
    clock = FakeClock()

    logs = iter(
        [
            ["event=master_missing"],
            ["event=leadership_promotion_started"],
            ["event=leadership_promoted"],
        ]
    )

    result = physical_runner.orchestrate_failover(
        evidence=physical_runner.initial_evidence(),
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: next(logs, []),
        read_peers=lambda: {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
        monotonic_clock=clock.monotonic,
        utc_clock=clock.utc,
        sleep=clock.sleep,
        timeout_seconds=5.0,
        poll_interval_seconds=0.1,
        expected_survivors=2,
        expected_survivor_ids={"NODE-B", "NODE-C"},
    )

    overlap = result["hub_master_overlap"]

    assert result["classification"] == "valid"
    assert result["active_split_brain_observed"] is False
    assert overlap["multiple_master_records_observed"] is False
    assert overlap["duration_ms"] is None
    assert overlap["first_observed_monotonic_seconds"] is None
    assert overlap["last_observed_monotonic_seconds"] is None


# ================================================================
# AXIS11_PHASE24I_OPERATIONAL_LIVENESS
# ================================================================


class Phase24IProcess:
    def __init__(self, return_code):
        self.return_code = return_code

    def poll(self):
        return self.return_code


class Phase24IResponse:
    def __init__(self, body):
        self.body = body
        self.closed = False

    def read(self):
        return self.body

    def close(self):
        self.closed = True


def test_phase24i_process_poll_distinguishes_alive_and_exited():
    alive = physical_runner.observe_process_liveness(
        Phase24IProcess(None)
    )

    exited = physical_runner.observe_process_liveness(
        Phase24IProcess(0)
    )

    assert alive == {
        "observable": True,
        "alive": True,
        "return_code": None,
        "source": "process-poll",
    }

    assert exited == {
        "observable": True,
        "alive": False,
        "return_code": 0,
        "source": "process-poll",
    }


def test_phase24i_liveness_endpoint_positive_observation():
    calls = []

    def opener(url, timeout):
        calls.append((url, timeout))
        return Phase24IResponse(
            b'{"alive": true, "node_id": "NODE-A"}'
        )

    result = physical_runner.fetch_node_liveness(
        8081,
        timeout_seconds=0.25,
        opener=opener,
    )

    assert calls == [
        (
            "http://127.0.0.1:8081/liveness",
            0.25,
        )
    ]

    assert result["observable"] is True
    assert result["reachable"] is True
    assert result["alive"] is True
    assert result["node_id"] == "NODE-A"
    assert result["error"] is None
    assert result["source"] == "runtime-liveness-endpoint"


def test_phase24i_liveness_endpoint_connection_failure_is_observed():
    def opener(url, timeout):
        raise ConnectionRefusedError("controlled refusal")

    result = physical_runner.fetch_node_liveness(
        8081,
        opener=opener,
    )

    assert result["observable"] is True
    assert result["reachable"] is False
    assert result["alive"] is False
    assert result["node_id"] is None
    assert "ConnectionRefusedError" in result["error"]
    assert "controlled refusal" in result["error"]


def test_phase24i_combined_observer_confirms_failed_master_down():
    def endpoint_probe(web_port):
        assert web_port == 8081
        return {
            "observable": True,
            "reachable": False,
            "alive": False,
            "node_id": None,
            "url": (
                "http://127.0.0.1:8081/liveness"
            ),
            "error": "ConnectionRefusedError: controlled",
            "source": "runtime-liveness-endpoint",
        }

    result = (
        physical_runner
        .observe_failed_master_operational_liveness(
            node_id="NODE-A",
            process=Phase24IProcess(0),
            web_port=8081,
            endpoint_probe=endpoint_probe,
        )
    )

    assert result["node_id"] == "NODE-A"
    assert result["process"]["alive"] is False
    assert result["endpoint"]["alive"] is False
    assert result["observations_agree"] is True
    assert result["operationally_alive"] is False

    assert (
        "Hub registry presence"
        in result["semantics"]
    )


def test_phase24i_combined_observer_confirms_live_master():
    def endpoint_probe(web_port):
        return {
            "observable": True,
            "reachable": True,
            "alive": True,
            "node_id": "NODE-A",
            "url": (
                "http://127.0.0.1:8081/liveness"
            ),
            "error": None,
            "source": "runtime-liveness-endpoint",
        }

    result = (
        physical_runner
        .observe_failed_master_operational_liveness(
            node_id="NODE-A",
            process=Phase24IProcess(None),
            web_port=8081,
            endpoint_probe=endpoint_probe,
        )
    )

    assert result["observations_agree"] is True
    assert result["operationally_alive"] is True


def test_phase24i_disagreement_is_inconclusive_not_false():
    def endpoint_probe(web_port):
        return {
            "observable": True,
            "reachable": False,
            "alive": False,
            "node_id": None,
            "url": (
                "http://127.0.0.1:8081/liveness"
            ),
            "error": "controlled disagreement",
            "source": "runtime-liveness-endpoint",
        }

    result = (
        physical_runner
        .observe_failed_master_operational_liveness(
            node_id="NODE-A",
            process=Phase24IProcess(None),
            web_port=8081,
            endpoint_probe=endpoint_probe,
        )
    )

    assert result["process"]["alive"] is True
    assert result["endpoint"]["alive"] is False

    assert result["observations_agree"] is False

    # Critical scientific rule:
    # disagreement must remain inconclusive.
    assert result["operationally_alive"] is None


def test_phase24i_observer_does_not_accept_hub_state_as_input():
    import inspect

    signature = inspect.signature(
        physical_runner
        .observe_failed_master_operational_liveness
    )

    assert "peers" not in signature.parameters
    assert "hub_state" not in signature.parameters
    assert "active_split_brain" not in signature.parameters



# ================================================================
# AXIS11_PHASE24I3_LIVENESS_EVIDENCE
# ================================================================


def test_phase24i3_records_failed_master_down_independently():
    evidence = {}

    observation = {
        "node_id": "NODE-A",
        "process": {
            "observable": True,
            "alive": False,
            "return_code": 0,
            "source": "process-poll",
        },
        "endpoint": {
            "observable": True,
            "reachable": False,
            "alive": False,
            "node_id": None,
            "url": "http://127.0.0.1:8081/liveness",
            "error": "ConnectionRefusedError: controlled",
            "source": "runtime-liveness-endpoint",
        },
        "observations_agree": True,
        "operationally_alive": False,
    }

    entry = (
        physical_runner
        .record_operational_liveness_observation(
            evidence,
            node_id="NODE-A",
            observation=observation,
            observed_at_utc=(
                "2026-09-19T12:00:00+00:00"
            ),
            observed_monotonic=100.0,
        )
    )

    assert entry["node_id"] == "NODE-A"
    assert entry["operationally_alive"] is False
    assert entry["observations_agree"] is True

    assert (
        physical_runner.failed_master_operational_state(
            evidence,
            "NODE-A",
        )
        is False
    )

    assert (
        evidence["operational_liveness"]
        ["latest"]["NODE-A"]
        ["operationally_alive"]
        is False
    )


def test_phase24i3_preserves_liveness_observation_history():
    evidence = {}

    observations = [
        {
            "node_id": "NODE-A",
            "process": {"alive": True},
            "endpoint": {"alive": True},
            "observations_agree": True,
            "operationally_alive": True,
        },
        {
            "node_id": "NODE-A",
            "process": {"alive": False},
            "endpoint": {"alive": False},
            "observations_agree": True,
            "operationally_alive": False,
        },
    ]

    for index, observation in enumerate(observations):
        physical_runner.record_operational_liveness_observation(
            evidence,
            node_id="NODE-A",
            observation=observation,
            observed_at_utc=(
                f"2026-09-19T12:00:0{index}+00:00"
            ),
            observed_monotonic=100.0 + index,
        )

    history = (
        evidence["operational_liveness"]
        ["observations"]
    )

    assert len(history) == 2
    assert history[0]["operationally_alive"] is True
    assert history[1]["operationally_alive"] is False

    assert (
        physical_runner.failed_master_operational_state(
            evidence,
            "NODE-A",
        )
        is False
    )


def test_phase24i3_inconclusive_state_remains_none():
    evidence = {}

    observation = {
        "node_id": "NODE-A",
        "process": {"alive": True},
        "endpoint": {"alive": False},
        "observations_agree": False,
        "operationally_alive": None,
    }

    physical_runner.record_operational_liveness_observation(
        evidence,
        node_id="NODE-A",
        observation=observation,
        observed_at_utc=(
            "2026-09-19T12:00:00+00:00"
        ),
        observed_monotonic=100.0,
    )

    assert (
        physical_runner.failed_master_operational_state(
            evidence,
            "NODE-A",
        )
        is None
    )


def test_phase24i3_missing_liveness_evidence_is_none():
    assert (
        physical_runner.failed_master_operational_state(
            {},
            "NODE-A",
        )
        is None
    )


def test_phase24i3_rejects_node_identity_mismatch():
    import pytest

    observation = {
        "node_id": "NODE-B",
        "process": {"alive": False},
        "endpoint": {"alive": False},
        "observations_agree": True,
        "operationally_alive": False,
    }

    with pytest.raises(
        ValueError,
        match="node_id does not match",
    ):
        (
            physical_runner
            .record_operational_liveness_observation(
                {},
                node_id="NODE-A",
                observation=observation,
                observed_at_utc=(
                    "2026-09-19T12:00:00+00:00"
                ),
                observed_monotonic=100.0,
            )
        )


def test_phase24i3_rejects_nonfinite_monotonic_time():
    import pytest

    observation = {
        "node_id": "NODE-A",
        "process": {"alive": False},
        "endpoint": {"alive": False},
        "observations_agree": True,
        "operationally_alive": False,
    }

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        (
            physical_runner
            .record_operational_liveness_observation(
                {},
                node_id="NODE-A",
                observation=observation,
                observed_at_utc=(
                    "2026-09-19T12:00:00+00:00"
                ),
                observed_monotonic=float("nan"),
            )
        )


def test_phase24i3_recording_does_not_change_classification():
    evidence = {
        "timeline": {
            "t0": {},
            "t1": {},
            "t2": {},
            "t3": {},
            "t4": {},
        },
        "promoted_node": "NODE-C",
        "converged": True,
        "active_split_brain_observed": True,
    }

    observation = {
        "node_id": "NODE-A",
        "process": {"alive": False},
        "endpoint": {"alive": False},
        "observations_agree": True,
        "operationally_alive": False,
    }

    physical_runner.record_operational_liveness_observation(
        evidence,
        node_id="NODE-A",
        observation=observation,
        observed_at_utc=(
            "2026-09-19T12:00:00+00:00"
        ),
        observed_monotonic=100.0,
    )

    recorder = physical_runner.TimelineRecorder()

    for index, event in enumerate(
        physical_runner.TIMELINE_EVENTS
    ):
        recorder.record(
            event,
            monotonic_seconds=100.0 + index,
            observed_at_utc=(
                "2026-09-19T12:00:00+00:00"
            ),
            source="phase24i3-test",
            detail=event,
        )

    result = physical_runner.classify_run(
        evidence,
        recorder,
        promoted_node="NODE-C",
        converged=True,
        active_split_brain_observed=True,
    )

    # Phase 24I.3 is evidence-only.
    # Legacy classification remains authoritative.
    assert result["classification"] == "invalid"
    assert result["active_split_brain_observed"] is True



# AXIS11_FINAL_BENCHMARK_INTEGRATION_TESTS


def test_final_integration_malformed_endpoint_is_inconclusive():
    class Response:
        def read(self):
            return b"not-json"

        def close(self):
            pass

    def opener(url, timeout):
        return Response()

    result = physical_runner.fetch_node_liveness(
        8081,
        opener=opener,
    )

    assert result["reachable"] is True
    assert result["observable"] is False
    assert result["alive"] is None


def test_final_integration_wrong_endpoint_identity_is_inconclusive():
    class Process:
        def poll(self):
            return None

    def probe(port):
        return {
            "observable": True,
            "reachable": True,
            "alive": True,
            "node_id": "NODE-X",
        }

    result = (
        physical_runner
        .observe_failed_master_operational_liveness(
            node_id="NODE-A",
            process=Process(),
            web_port=8081,
            endpoint_probe=probe,
        )
    )

    assert result["observations_agree"] is False
    assert result["operationally_alive"] is None


def test_final_integration_hub_overlap_dead_master_not_operational_split():
    evidence = physical_runner.initial_evidence()

    clock_values = iter([
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
        109.0,
        110.0,
        111.0,
        112.0,
        113.0,
        114.0,
        115.0,
        116.0,
        117.0,
        118.0,
        119.0,
        120.0,
        121.0,
        122.0,
        123.0,
        124.0,
        125.0,
        126.0,
        127.0,
        128.0,
        129.0,
        130.0,
    ])

    def clock():
        return next(clock_values)

    log_batches = iter([
        [
            "master_missing",
            "leadership_promotion_started",
            "leadership_promoted",
        ],
        [],
    ])

    peer_batches = iter([
        {
            "NODE-A": {"role": "MASTER"},
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
        {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
    ])

    def read_logs():
        return next(log_batches, [])

    def read_peers():
        return next(
            peer_batches,
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        )

    def dead_master():
        return {
            "node_id": "NODE-A",
            "process": {"alive": False},
            "endpoint": {
                "observable": True,
                "reachable": False,
                "alive": False,
                "node_id": None,
            },
            "observations_agree": True,
            "operationally_alive": False,
        }

    result = physical_runner.orchestrate_failover(
        evidence=evidence,
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=read_logs,
        read_peers=read_peers,
        monotonic_clock=clock,
        utc_clock=lambda: "2026-09-20T12:00:00+00:00",
        sleep=lambda seconds: None,
        timeout_seconds=100.0,
        expected_survivor_ids={"NODE-B", "NODE-C"},
        observe_failed_master_liveness=dead_master,
    )

    assert (
        result["hub_master_overlap"]
        ["multiple_master_records_observed"]
        is True
    )
    assert (
        result["operational_split_brain"]["observed"]
        is False
    )
    assert result["classification"] == "valid"


def test_final_integration_live_failed_master_is_operational_split():
    evidence = physical_runner.initial_evidence()

    clock_values = iter([
        200.0,
        201.0,
        202.0,
        203.0,
        204.0,
        205.0,
        206.0,
        207.0,
        208.0,
        209.0,
        210.0,
        211.0,
        212.0,
        213.0,
        214.0,
        215.0,
        216.0,
        217.0,
        218.0,
        219.0,
        220.0,
        221.0,
        222.0,
        223.0,
        224.0,
        225.0,
        226.0,
        227.0,
        228.0,
        229.0,
        230.0,
    ])

    def clock():
        return next(clock_values)

    log_batches = iter([
        [
            "master_missing",
            "leadership_promotion_started",
            "leadership_promoted",
        ],
        [],
    ])

    peer_batches = iter([
        {
            "NODE-A": {"role": "MASTER"},
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
        {
            "NODE-B": {"role": "FOLLOWER"},
            "NODE-C": {"role": "MASTER"},
        },
    ])

    def live_master():
        return {
            "node_id": "NODE-A",
            "process": {"alive": True},
            "endpoint": {
                "observable": True,
                "reachable": True,
                "alive": True,
                "node_id": "NODE-A",
            },
            "observations_agree": True,
            "operationally_alive": True,
        }

    result = physical_runner.orchestrate_failover(
        evidence=evidence,
        failed_master_id="NODE-A",
        terminate_master=lambda: None,
        read_log_lines=lambda: next(log_batches, []),
        read_peers=lambda: next(
            peer_batches,
            {
                "NODE-B": {"role": "FOLLOWER"},
                "NODE-C": {"role": "MASTER"},
            },
        ),
        monotonic_clock=clock,
        utc_clock=lambda: "2026-09-20T12:00:00+00:00",
        sleep=lambda seconds: None,
        timeout_seconds=100.0,
        expected_survivor_ids={"NODE-B", "NODE-C"},
        observe_failed_master_liveness=live_master,
    )

    assert (
        result["operational_split_brain"]["observed"]
        is True
    )
    assert result["classification"] == "invalid"
    assert "split-brain" in result["invalid_reason"]

def test_baseline_from_hub_state_accepts_exact_three_node_topology():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "FOLLOWER"},
    }

    baseline = physical_runner.baseline_from_hub_state(
        peers,
        expected_node_ids={
            "NODE-A",
            "NODE-B",
            "NODE-C",
        },
        expected_master_id="NODE-A",
    )

    assert baseline == {
        "peer_ids": [
            "NODE-A",
            "NODE-B",
            "NODE-C",
        ],
        "masters": ["NODE-A"],
        "master_count": 1,
        "active_split_brain": False,
    }


def test_baseline_from_hub_state_rejects_missing_node():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
    }

    baseline = physical_runner.baseline_from_hub_state(
        peers,
        expected_node_ids={
            "NODE-A",
            "NODE-B",
            "NODE-C",
        },
        expected_master_id="NODE-A",
    )

    assert baseline is None


def test_baseline_from_hub_state_rejects_wrong_master():
    peers = {
        "NODE-A": {"role": "FOLLOWER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    baseline = physical_runner.baseline_from_hub_state(
        peers,
        expected_node_ids={
            "NODE-A",
            "NODE-B",
            "NODE-C",
        },
        expected_master_id="NODE-A",
    )

    assert baseline is None


def test_baseline_from_hub_state_rejects_multiple_masters():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "MASTER"},
    }

    baseline = physical_runner.baseline_from_hub_state(
        peers,
        expected_node_ids={
            "NODE-A",
            "NODE-B",
            "NODE-C",
        },
        expected_master_id="NODE-A",
    )

    assert baseline is None


def test_baseline_from_hub_state_rejects_extra_node():
    peers = {
        "NODE-A": {"role": "MASTER"},
        "NODE-B": {"role": "FOLLOWER"},
        "NODE-C": {"role": "FOLLOWER"},
        "NODE-D": {"role": "FOLLOWER"},
    }

    baseline = physical_runner.baseline_from_hub_state(
        peers,
        expected_node_ids={
            "NODE-A",
            "NODE-B",
            "NODE-C",
        },
        expected_master_id="NODE-A",
    )

    assert baseline is None
