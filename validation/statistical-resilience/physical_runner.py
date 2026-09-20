from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any


RUNNER_SCHEMA = "nexus.axis11.physical-runner.v1"
DEFAULT_HUB_URL = "http://127.0.0.1:8500"
DEFAULT_CLUSTER_SIZE = 3
DEFAULT_PROMOTION_TIMEOUT_SECONDS = 70.0


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    web_port: int
    tcp_port: int
    role: str

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id must not be empty")

        if not 1 <= self.web_port <= 65535:
            raise ValueError("web_port must be between 1 and 65535")

        if not 1 <= self.tcp_port <= 65535:
            raise ValueError("tcp_port must be between 1 and 65535")

        normalized_role = self.role.upper()
        if normalized_role not in {"MASTER", "FOLLOWER"}:
            raise ValueError("role must be MASTER or FOLLOWER")

        object.__setattr__(self, "role", normalized_role)


DEFAULT_NODES = (
    NodeSpec("NODE-A", 8081, 9091, "MASTER"),
    NodeSpec("NODE-B", 8082, 9092, "FOLLOWER"),
    NodeSpec("NODE-C", 8083, 9093, "FOLLOWER"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_environment(
    *,
    secret_key: str,
    hub_url: str = DEFAULT_HUB_URL,
    cluster_size: int = DEFAULT_CLUSTER_SIZE,
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    if not secret_key.strip():
        raise ValueError("secret_key must not be empty")

    if cluster_size < 1:
        raise ValueError("cluster_size must be greater than zero")

    env = dict(base or {})
    env["NEXUS_SECRET_KEY"] = secret_key
    env["NEXUS_HUB_URL"] = hub_url
    env["NEXUS_CLUSTER_SIZE"] = str(cluster_size)
    return env


def build_node_command(
    python_executable: str,
    spec: NodeSpec,
) -> list[str]:
    return [
        python_executable,
        "nexus_distributed_core.py",
        spec.node_id,
        str(spec.web_port),
        str(spec.tcp_port),
        spec.role,
    ]


def build_hub_command(python_executable: str) -> list[str]:
    return [
        python_executable,
        "nexus_rendezvous.py",
    ]


def validate_topology(nodes: tuple[NodeSpec, ...]) -> None:
    if len(nodes) != DEFAULT_CLUSTER_SIZE:
        raise ValueError("Axis 11 physical topology requires exactly 3 nodes")

    node_ids = [node.node_id for node in nodes]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("node_id values must be unique")

    web_ports = [node.web_port for node in nodes]
    tcp_ports = [node.tcp_port for node in nodes]

    all_ports = web_ports + tcp_ports
    if len(set(all_ports)) != len(all_ports):
        raise ValueError("all node ports must be unique")

    masters = [node for node in nodes if node.role == "MASTER"]
    followers = [node for node in nodes if node.role == "FOLLOWER"]

    if len(masters) != 1:
        raise ValueError("topology requires exactly one initial MASTER")

    if len(followers) != 2:
        raise ValueError("topology requires exactly two initial FOLLOWER nodes")


def deterministic_candidate(
    nodes: tuple[NodeSpec, ...],
    *,
    failed_master_id: str,
) -> str:
    candidates = sorted(
        node.node_id
        for node in nodes
        if node.node_id != failed_master_id
        and node.role == "FOLLOWER"
    )

    if not candidates:
        raise ValueError("no eligible follower candidate")

    return candidates[-1]


def stop_process(
    process: subprocess.Popen[Any],
    *,
    wait_seconds: float = 3.0,
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=wait_seconds)


def initial_evidence() -> dict[str, Any]:
    return {
        "schema": RUNNER_SCHEMA,
        "classification": "pending",
        "captured_at_utc": utc_now(),
        "experiment": "three-node-master-loss-failover",
        "topology": {
            "configured_cluster_size": DEFAULT_CLUSTER_SIZE,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "web_port": node.web_port,
                    "tcp_port": node.tcp_port,
                    "initial_role": node.role,
                }
                for node in DEFAULT_NODES
            ],
        },
        "timeline": {
            "t0": None,
            "t1": None,
            "t2": None,
            "t3": None,
            "t4": None,
        },
        "timing_ms": {},
        "promoted_node": None,
        "converged": False,
        "active_split_brain_observed": False,
        "invalid_reason": None,
    }


def evidence_directory(root: str | Path, run_id: str) -> Path:
    normalized = run_id.strip()

    if not normalized:
        raise ValueError("run_id must not be empty")

    if "/" in normalized or "\\" in normalized:
        raise ValueError("run_id must not contain path separators")

    return Path(root) / normalized

TIMELINE_EVENTS = ("t0", "t1", "t2", "t3", "t4")


@dataclass(frozen=True)
class Observation:
    event: str
    monotonic_seconds: float
    observed_at_utc: str
    source: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.event not in TIMELINE_EVENTS:
            raise ValueError(f"unknown timeline event: {self.event}")

        if not __import__("math").isfinite(
            self.monotonic_seconds
        ):
            raise ValueError(
                "monotonic_seconds must be finite"
            )

        if self.monotonic_seconds < 0:
            raise ValueError(
                "monotonic_seconds must be non-negative"
            )

        if not self.source.strip():
            raise ValueError("source must not be empty")


class TimelineRecorder:
    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}

    def record(
        self,
        event: str,
        *,
        monotonic_seconds: float,
        observed_at_utc: str,
        source: str,
        detail: str | None = None,
    ) -> Observation:
        if event in self._observations:
            raise ValueError(f"timeline event already recorded: {event}")

        observation = Observation(
            event=event,
            monotonic_seconds=float(monotonic_seconds),
            observed_at_utc=observed_at_utc,
            source=source,
            detail=detail,
        )

        previous_events = TIMELINE_EVENTS[
            :TIMELINE_EVENTS.index(event)
        ]

        previous_observations = [
            self._observations[name]
            for name in previous_events
            if name in self._observations
        ]

        if previous_observations:
            latest = max(
                item.monotonic_seconds
                for item in previous_observations
            )

            if observation.monotonic_seconds < latest:
                raise ValueError(
                    "timeline monotonic order violation"
                )

        self._observations[event] = observation
        return observation

    def get(self, event: str) -> Observation | None:
        if event not in TIMELINE_EVENTS:
            raise ValueError(f"unknown timeline event: {event}")

        return self._observations.get(event)

    def complete(self) -> bool:
        return all(
            event in self._observations
            for event in TIMELINE_EVENTS
        )

    def as_evidence(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for event in TIMELINE_EVENTS:
            observation = self._observations.get(event)

            if observation is None:
                result[event] = None
                continue

            result[event] = {
                "observed_at_utc": observation.observed_at_utc,
                "source": observation.source,
                "detail": observation.detail,
            }

        return result

    def timing_ms(self) -> dict[str, float]:
        required = {
            event: self._observations.get(event)
            for event in TIMELINE_EVENTS
        }

        if required["t0"] is None:
            return {}

        t0 = required["t0"]

        result: dict[str, float] = {}

        intervals = (
            ("t0_to_t1", "t0", "t1"),
            ("t1_to_t2", "t1", "t2"),
            ("t2_to_t3", "t2", "t3"),
            ("t1_to_t3", "t1", "t3"),
            ("t3_to_t4", "t3", "t4"),
            ("t0_to_t4", "t0", "t4"),
        )

        for label, start_name, end_name in intervals:
            start = required[start_name]
            end = required[end_name]

            if start is None or end is None:
                continue

            result[label] = round(
                (
                    end.monotonic_seconds
                    - start.monotonic_seconds
                ) * 1000.0,
                3,
            )

        return result


def apply_timeline(
    evidence: dict[str, Any],
    recorder: TimelineRecorder,
) -> dict[str, Any]:
    updated = dict(evidence)
    updated["timeline"] = recorder.as_evidence()
    updated["timing_ms"] = recorder.timing_ms()
    return updated

def classify_run(
    evidence: dict[str, Any],
    recorder: TimelineRecorder,
    *,
    promoted_node: str | None,
    converged: bool,
    active_split_brain_observed: bool,
    invalid_reason: str | None = None,
) -> dict[str, Any]:
    updated = apply_timeline(evidence, recorder)

    normalized_promoted = (
        promoted_node.strip()
        if isinstance(promoted_node, str)
        else None
    )

    normalized_reason = (
        invalid_reason.strip()
        if isinstance(invalid_reason, str)
        else None
    )

    valid = (
        recorder.complete()
        and bool(normalized_promoted)
        and converged is True
        and active_split_brain_observed is False
        and normalized_reason is None
    )

    updated["promoted_node"] = normalized_promoted
    updated["converged"] = converged
    updated["active_split_brain_observed"] = (
        active_split_brain_observed
    )

    if valid:
        updated["classification"] = "valid"
        updated["invalid_reason"] = None
        return updated

    if normalized_reason is None:
        reasons: list[str] = []

        if not recorder.complete():
            missing = [
                event
                for event in TIMELINE_EVENTS
                if recorder.get(event) is None
            ]
            reasons.append(
                "incomplete timeline: " + ", ".join(missing)
            )

        if not normalized_promoted:
            reasons.append("promoted node not observed")

        if converged is not True:
            reasons.append("external convergence not confirmed")

        if active_split_brain_observed is True:
            reasons.append("active split-brain observed")

        normalized_reason = "; ".join(reasons)

    if not normalized_reason:
        raise ValueError("invalid run requires invalid_reason")

    updated["classification"] = "invalid"
    updated["invalid_reason"] = normalized_reason
    return updated


def save_evidence_json(
    path: str | Path,
    evidence: dict[str, Any],
) -> Path:
    import json

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(
        evidence,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"

    target.write_text(
        serialized,
        encoding="utf-8",
        newline="\n",
    )

    return target

def observe_hub_state(
    peers: dict[str, Any],
    *,
    failed_master_id: str,
) -> dict[str, Any]:
    if not isinstance(peers, dict):
        raise ValueError("peers must be a mapping")

    normalized: dict[str, str] = {}

    for node_id, raw in peers.items():
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("peer node_id must be non-empty")

        if not isinstance(raw, dict):
            raise ValueError("peer record must be a mapping")

        role = raw.get("role")

        if not isinstance(role, str):
            raise ValueError("peer role must be a string")

        role = role.upper()

        if role not in {"MASTER", "FOLLOWER"}:
            raise ValueError("peer role is invalid")

        normalized[node_id] = role

    masters = sorted(
        node_id
        for node_id, role in normalized.items()
        if role == "MASTER"
    )

    surviving = sorted(
        node_id
        for node_id in normalized
        if node_id != failed_master_id
    )

    return {
        "failed_master_present": (
            failed_master_id in normalized
        ),
        "masters": masters,
        "master_count": len(masters),
        "surviving_nodes": surviving,
        "surviving_count": len(surviving),
        "promoted_node": (
            masters[0]
            if len(masters) == 1
            and masters[0] != failed_master_id
            else None
        ),
        "active_split_brain": len(masters) > 1,
    }


def convergence_from_hub_state(
    state: dict[str, Any],
    *,
    expected_survivors: int = 2,
    expected_survivor_ids: set[str] | None = None,
) -> bool:
    survivor_count_matches = (
        state.get("surviving_count") == expected_survivors
    )

    survivor_set_matches = True

    if expected_survivor_ids is not None:
        survivor_set_matches = (
            set(state.get("surviving_nodes", []))
            == set(expected_survivor_ids)
        )

    return (
        state.get("failed_master_present") is False
        and state.get("master_count") == 1
        and survivor_count_matches
        and survivor_set_matches
        and state.get("active_split_brain") is False
        and bool(state.get("promoted_node"))
    )


LOG_EVENT_MAP = {
    "master_missing": "t1",
    "leadership_promotion_started": "t2",
    "leadership_promoted": "t3",
}


def observe_log_event(line: str) -> str | None:
    if not isinstance(line, str):
        raise ValueError("log line must be a string")

    matches = [
        timeline_event
        for marker, timeline_event in LOG_EVENT_MAP.items()
        if marker in line
    ]

    if len(matches) > 1:
        raise ValueError(
            "ambiguous log line contains multiple timeline events"
        )

    if not matches:
        return None

    return matches[0]


def observe_external_t4(
    peers: dict[str, Any],
    *,
    failed_master_id: str,
    expected_survivors: int = 2,
) -> tuple[bool, str | None, bool]:
    state = observe_hub_state(
        peers,
        failed_master_id=failed_master_id,
    )

    converged = convergence_from_hub_state(
        state,
        expected_survivors=expected_survivors,
    )

    return (
        converged,
        state["promoted_node"],
        state["active_split_brain"],
    )


# ================================================================
# AXIS11_PHASE24I_OPERATIONAL_LIVENESS
# ================================================================

def observe_process_liveness(process: Any) -> dict[str, Any]:
    """Observe local child-process liveness without using Hub state.

    subprocess.Popen.poll() returning None means that the child has
    not terminated at the instant of observation.  A numeric return
    code means that the process has exited.

    This is deliberately independent from the Hub registry.
    """

    poll = getattr(process, "poll", None)

    if not callable(poll):
        raise ValueError("process must provide poll()")

    return_code = poll()

    return {
        "observable": True,
        "alive": return_code is None,
        "return_code": return_code,
        "source": "process-poll",
    }


def fetch_node_liveness(
    web_port: int,
    *,
    host: str = "127.0.0.1",
    timeout_seconds: float = 1.0,
    opener: Any = None,
) -> dict[str, Any]:
    """Fetch the runtime /liveness endpoint.

    Transport failure and invalid endpoint evidence are distinct.

    reachable=False means that no valid HTTP response was obtained.
    reachable=True with observable=False means that the endpoint
    responded but its payload could not support a liveness claim.
    """
    import json
    from urllib.request import urlopen

    if not 1 <= int(web_port) <= 65535:
        raise ValueError("web_port must be between 1 and 65535")

    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must not be empty")

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    open_url = opener if opener is not None else urlopen
    url = f"http://{host.strip()}:{int(web_port)}/liveness"

    try:
        response = open_url(
            url,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return {
            "observable": True,
            "reachable": False,
            "alive": False,
            "node_id": None,
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "source": "runtime-liveness-endpoint",
        }

    try:
        try:
            body = response.read()
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

        payload = json.loads(body.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError(
                "liveness response must be a JSON object"
            )

        if payload.get("alive") is not True:
            raise ValueError(
                "liveness response must explicitly report alive=true"
            )

        node_id = payload.get("node_id")

        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(
                "liveness response must contain node_id"
            )

        return {
            "observable": True,
            "reachable": True,
            "alive": True,
            "node_id": node_id.strip(),
            "url": url,
            "error": None,
            "source": "runtime-liveness-endpoint",
        }

    except Exception as exc:
        return {
            "observable": False,
            "reachable": True,
            "alive": None,
            "node_id": None,
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "source": "runtime-liveness-endpoint",
        }


def observe_failed_master_operational_liveness(
    *,
    node_id: str,
    process: Any,
    web_port: int,
    endpoint_probe: Any = None,
) -> dict[str, Any]:
    """Observe failed-master liveness independently from Hub state.

    A locally managed child that has exited cannot be treated as
    operationally alive merely because the Hub still has a record.

    Process alive + matching live endpoint confirms operational
    liveness. Process exited + endpoint unreachable confirms down.
    All other combinations are retained as inconclusive.
    """
    normalized_node_id = str(node_id).strip()

    if not normalized_node_id:
        raise ValueError("node_id must not be empty")

    process_observation = observe_process_liveness(process)

    probe = (
        endpoint_probe
        if endpoint_probe is not None
        else fetch_node_liveness
    )

    endpoint_observation = probe(web_port)

    if not isinstance(endpoint_observation, dict):
        raise ValueError(
            "endpoint_probe must return a mapping"
        )

    process_alive = process_observation.get("alive")

    endpoint_observable = (
        endpoint_observation.get("observable") is True
    )
    endpoint_reachable = (
        endpoint_observation.get("reachable") is True
    )
    endpoint_alive = endpoint_observation.get("alive")
    endpoint_node_id = endpoint_observation.get("node_id")

    operationally_alive = None
    agreement = False

    if process_alive is False and endpoint_reachable is False:
        operationally_alive = False
        agreement = True

    elif (
        process_alive is True
        and endpoint_observable
        and endpoint_reachable
        and endpoint_alive is True
        and endpoint_node_id == normalized_node_id
    ):
        operationally_alive = True
        agreement = True

    return {
        "node_id": normalized_node_id,
        "process": process_observation,
        "endpoint": endpoint_observation,
        "observations_agree": agreement,
        "operationally_alive": operationally_alive,
        "semantics": (
            "Operational liveness is derived from independent "
            "process-poll and runtime /liveness observations. "
            "Hub registry presence or Hub role records are not "
            "used as proof of process liveness."
        ),
    }



# ================================================================
# AXIS11_PHASE24I3_LIVENESS_EVIDENCE
# ================================================================

def record_operational_liveness_observation(
    evidence: dict[str, Any],
    *,
    node_id: str,
    observation: dict[str, Any],
    observed_at_utc: str,
    observed_monotonic: float,
) -> dict[str, Any]:
    """Append an independent operational-liveness observation.

    This function records evidence only.  It does not classify the
    run and does not reinterpret Hub registry observations.
    """

    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a mapping")

    if not isinstance(observation, dict):
        raise ValueError("observation must be a mapping")

    normalized_node_id = str(node_id).strip()

    if not normalized_node_id:
        raise ValueError("node_id must not be empty")

    if observation.get("node_id") != normalized_node_id:
        raise ValueError(
            "observation node_id does not match requested node_id"
        )

    import math

    monotonic_value = float(observed_monotonic)

    if not math.isfinite(monotonic_value):
        raise ValueError(
            "observed_monotonic must be finite"
        )

    if monotonic_value < 0:
        raise ValueError(
            "observed_monotonic must be nonnegative"
        )

    utc_value = str(observed_at_utc).strip()

    if not utc_value:
        raise ValueError(
            "observed_at_utc must not be empty"
        )

    section = evidence.setdefault(
        "operational_liveness",
        {
            "semantics": (
                "Independent process and runtime endpoint "
                "observations. Hub registry membership and Hub "
                "role records are not proof of operational "
                "process liveness."
            ),
            "observations": [],
        },
    )

    observations = section.setdefault(
        "observations",
        [],
    )

    entry = {
        "node_id": normalized_node_id,
        "observed_at_utc": utc_value,
        "observed_monotonic": monotonic_value,
        "operationally_alive": observation.get(
            "operationally_alive"
        ),
        "observations_agree": observation.get(
            "observations_agree"
        ),
        "process": observation.get("process"),
        "endpoint": observation.get("endpoint"),
    }

    observations.append(entry)

    # Keep a compact latest-state view without deleting history.
    latest = section.setdefault("latest", {})
    latest[normalized_node_id] = entry

    return entry


def failed_master_operational_state(
    evidence: dict[str, Any],
    failed_master_id: str,
) -> Any:
    """Return the latest independently observed operational state.

    True  -> independently observed alive.
    False -> independently observed down.
    None  -> absent or inconclusive evidence.
    """

    section = evidence.get("operational_liveness")

    if not isinstance(section, dict):
        return None

    latest = section.get("latest")

    if not isinstance(latest, dict):
        return None

    entry = latest.get(str(failed_master_id).strip())

    if not isinstance(entry, dict):
        return None

    value = entry.get("operationally_alive")

    if value is True:
        return True

    if value is False:
        return False

    return None


def fetch_peers(
    hub_url: str,
    *,
    timeout_seconds: float = 2.0,
    opener: Any = None,
) -> dict[str, Any]:
    import json
    from urllib.request import urlopen

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    normalized = hub_url.rstrip("/")
    if not normalized:
        raise ValueError("hub_url must not be empty")

    open_url = opener or urlopen

    response = open_url(
        normalized + "/peers",
        timeout=timeout_seconds,
    )

    try:
        payload = response.read()
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    decoded = json.loads(payload.decode("utf-8"))

    if not isinstance(decoded, dict):
        raise ValueError("Hub /peers response must be a mapping")

    return decoded


class IncrementalLogReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._offset = 0

    @property
    def offset(self) -> int:
        return self._offset

    def read_new_lines(self) -> list[str]:
        if not self.path.exists():
            return []

        size = self.path.stat().st_size

        if size < self._offset:
            # Log was truncated/recreated.
            self._offset = 0

        with self.path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline=None,
        ) as handle:
            handle.seek(self._offset)
            lines = handle.readlines()
            self._offset = handle.tell()

        return [
            line.rstrip("\r\n")
            for line in lines
        ]


def start_process(
    command: list[str],
    *,
    environment: dict[str, str],
    stdout_path: str | Path,
    stderr_path: str | Path,
    popen_factory: Any = None,
) -> tuple[Any, Any, Any]:
    if not command:
        raise ValueError("command must not be empty")

    stdout_target = Path(stdout_path)
    stderr_target = Path(stderr_path)

    stdout_target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    stderr_target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    stdout_handle = stdout_target.open(
        "w",
        encoding="utf-8",
        newline="\n",
    )
    stderr_handle = stderr_target.open(
        "w",
        encoding="utf-8",
        newline="\n",
    )

    factory = popen_factory or subprocess.Popen

    try:
        process = factory(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
    except Exception:
        stdout_handle.close()
        stderr_handle.close()
        raise

    return process, stdout_handle, stderr_handle


def close_process_handles(
    *handles: Any,
) -> None:
    for handle in handles:
        if handle is None:
            continue

        close = getattr(handle, "close", None)

        if callable(close) and not getattr(
            handle,
            "closed",
            False,
        ):
            close()

def orchestrate_failover(
    *,
    evidence: dict[str, Any],
    failed_master_id: str,
    terminate_master: Any,
    read_log_lines: Any,
    read_peers: Any,
    monotonic_clock: Any,
    utc_clock: Any,
    sleep: Any,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.05,
    expected_survivors: int = 2,
    expected_survivor_ids: set[str] | None = None,
    observe_failed_master_liveness: Any = None,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    if poll_interval_seconds <= 0:
        raise ValueError(
            "poll_interval_seconds must be positive"
        )

    recorder = TimelineRecorder()

    t0_monotonic = float(monotonic_clock())

    recorder.record(
        "t0",
        monotonic_seconds=t0_monotonic,
        observed_at_utc=str(utc_clock()),
        source="runner",
        detail="controlled master termination initiated",
    )

    terminate_master()

    deadline = t0_monotonic + timeout_seconds

    promoted_node: str | None = None
    converged = False
    operational_split_brain_observed = False
    operational_liveness_inconclusive = False

    # AXIS11_PHASE24F_MASTER_OVERLAP
    #
    # This instrumentation describes the Hub-observed role view.
    # It does not independently prove simultaneous live execution
    # of multiple MASTER processes.
    hub_master_sets_observed: list[list[str]] = []
    hub_multiple_master_records_observed = False
    overlap_first_monotonic: float | None = None
    overlap_last_monotonic: float | None = None

    invalid_reason: str | None = None

    while float(monotonic_clock()) <= deadline:
        for line in read_log_lines():
            event = observe_log_event(line)

            if event is None:
                continue

            if recorder.get(event) is not None:
                continue

            # T2/T3 cannot be accepted before their predecessor.
            if event == "t2" and recorder.get("t1") is None:
                continue

            if event == "t3" and recorder.get("t2") is None:
                continue

            recorder.record(
                event,
                monotonic_seconds=float(monotonic_clock()),
                observed_at_utc=str(utc_clock()),
                source="node-log",
                detail=line,
            )

        peers = read_peers()

        state = observe_hub_state(
            peers,
            failed_master_id=failed_master_id,
        )

        if observe_failed_master_liveness is not None:
            operational_observation = (
                observe_failed_master_liveness()
            )

            record_operational_liveness_observation(
                evidence,
                node_id=failed_master_id,
                observation=operational_observation,
                observed_at_utc=str(utc_clock()),
                observed_monotonic=float(monotonic_clock()),
            )

            failed_master_alive = (
                operational_observation.get(
                    "operationally_alive"
                )
            )

            survivor_master_present = any(
                master != failed_master_id
                for master in state["masters"]
            )

            if (
                failed_master_alive is True
                and survivor_master_present
            ):
                operational_split_brain_observed = True

            if failed_master_alive is None:
                operational_liveness_inconclusive = True

        current_masters = list(state["masters"])

        if (
            not hub_master_sets_observed
            or hub_master_sets_observed[-1] != current_masters
        ):
            hub_master_sets_observed.append(current_masters)

        if state["active_split_brain"]:
            hub_multiple_master_records_observed = True

            overlap_now = float(monotonic_clock())

            if overlap_first_monotonic is None:
                overlap_first_monotonic = overlap_now

            overlap_last_monotonic = overlap_now

        current_converged = convergence_from_hub_state(
            state,
            expected_survivors=expected_survivors,
            expected_survivor_ids=expected_survivor_ids,
        )

        if current_converged:
            promoted_node = state["promoted_node"]

            # External convergence alone does not finalize T4.
            # T3 must first be observed from the runtime log so
            # the measured timeline remains T0<T1<T2<T3<T4.
            if recorder.get("t3") is not None:
                converged = True

                if recorder.get("t4") is None:
                    recorder.record(
                        "t4",
                        monotonic_seconds=float(
                            monotonic_clock()
                        ),
                        observed_at_utc=str(utc_clock()),
                        source="hub",
                        detail=(
                            "externally observed converged MASTER "
                            + str(promoted_node)
                        ),
                    )

                break

        sleep(poll_interval_seconds)

    if not converged:
        invalid_reason = (
            "timeout before external convergence"
        )

    evidence = dict(evidence)

    overlap_duration_ms: float | None = None

    if (
        overlap_first_monotonic is not None
        and overlap_last_monotonic is not None
    ):
        overlap_duration_ms = round(
            max(
                0.0,
                (
                    overlap_last_monotonic
                    - overlap_first_monotonic
                )
                * 1000.0,
            ),
            3,
        )

    evidence["hub_master_overlap"] = {
        "multiple_master_records_observed": (
            hub_multiple_master_records_observed
        ),
        "master_sets_observed": hub_master_sets_observed,
        "first_observed_monotonic_seconds": (
            overlap_first_monotonic
        ),
        "last_observed_monotonic_seconds": (
            overlap_last_monotonic
        ),
        "duration_ms": overlap_duration_ms,
        "semantics": (
            "Hub-observed MASTER record overlap; "
            "does not independently prove simultaneous live "
            "MASTER process execution"
        ),
    }

    evidence["operational_split_brain"] = {
        "observed": operational_split_brain_observed,
        "liveness_inconclusive_observed": (
            operational_liveness_inconclusive
        ),
        "semantics": (
            "Operational split-brain requires independently "
            "observed failed-master liveness while a surviving "
            "node is also observed as MASTER. Hub registry "
            "overlap alone is not sufficient."
        ),
    }

    if (
        observe_failed_master_liveness is not None
        and operational_liveness_inconclusive
        and invalid_reason is None
    ):
        invalid_reason = (
            "operational liveness observation inconclusive"
        )

    # Preserve the frozen legacy contract for callers that do not
    # provide the independent operational-liveness observer.
    #
    # Prospective physical runs that provide the observer classify
    # split-brain from independent operational evidence instead of
    # treating Hub registry overlap as proof of simultaneous live
    # MASTER execution.
    classification_split_brain_observed = (
        operational_split_brain_observed
        if observe_failed_master_liveness is not None
        else hub_multiple_master_records_observed
    )

    return classify_run(
        evidence,
        recorder,
        promoted_node=promoted_node,
        converged=converged,
        active_split_brain_observed=(
            classification_split_brain_observed
        ),
        invalid_reason=invalid_reason,
    )

@dataclass(frozen=True)
class PhysicalRunLayout:
    root: Path
    run_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be non-empty")

        if any(
            token in self.run_id
            for token in ("/", "\\", "..")
        ):
            raise ValueError("run_id contains unsafe path syntax")

    @property
    def run_directory(self) -> Path:
        return self.root / self.run_id

    @property
    def logs_directory(self) -> Path:
        return self.run_directory / "logs"

    @property
    def state_directory(self) -> Path:
        return self.run_directory / "state"

    @property
    def evidence_path(self) -> Path:
        return self.run_directory / "benchmark-summary.json"

    def node_db_path(self, node_id: str) -> Path:
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be non-empty")

        if any(
            token in node_id
            for token in ("/", "\\", "..")
        ):
            raise ValueError("node_id contains unsafe path syntax")

        return self.state_directory / f"{node_id}.jsonl"

    def stdout_path(self, process_id: str) -> Path:
        if not isinstance(process_id, str) or not process_id.strip():
            raise ValueError("process_id must be non-empty")

        if any(
            token in process_id
            for token in ("/", "\\", "..")
        ):
            raise ValueError("process_id contains unsafe path syntax")

        return self.logs_directory / f"{process_id}.stdout.log"

    def stderr_path(self, process_id: str) -> Path:
        if not isinstance(process_id, str) or not process_id.strip():
            raise ValueError("process_id must be non-empty")

        if any(
            token in process_id
            for token in ("/", "\\", "..")
        ):
            raise ValueError("process_id contains unsafe path syntax")

        return self.logs_directory / f"{process_id}.stderr.log"


def build_physical_environment(
    *,
    secret_key: str,
    hub_url: str,
    cluster_size: int,
    db_path: str | Path | None = None,
    base_environment: dict[str, str] | None = None,
) -> dict[str, str]:
    import os

    if base_environment is None:
        env = os.environ.copy()
    else:
        env = dict(base_environment)

    env = build_environment(
        secret_key=secret_key,
        hub_url=hub_url,
        cluster_size=cluster_size,
        base=env,
    )

    if db_path is not None:
        env["NEXUS_DB_PATH"] = str(Path(db_path))

    return env


def prepare_run_layout(
    layout: PhysicalRunLayout,
) -> PhysicalRunLayout:
    if layout.run_directory.exists():
        raise FileExistsError(
            "physical run directory already exists: "
            + str(layout.run_directory)
        )

    layout.logs_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    layout.state_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    return layout


def physical_monotonic_clock() -> float:
    import time

    return time.perf_counter()


def physical_sleep(seconds: float) -> None:
    import time

    if seconds < 0:
        raise ValueError("sleep seconds must be non-negative")

    time.sleep(seconds)

def build_provenance(
    *,
    run_id: str,
    git_sha: str,
    python_version: str,
    platform_description: str,
    captured_at_utc: str,
    hub_url: str = DEFAULT_HUB_URL,
    nodes: tuple[NodeSpec, ...] = DEFAULT_NODES,
) -> dict[str, Any]:
    normalized_run_id = str(run_id).strip()
    normalized_git_sha = str(git_sha).strip()
    normalized_python = str(python_version).strip()
    normalized_platform = str(platform_description).strip()
    normalized_captured = str(captured_at_utc).strip()

    if not normalized_run_id:
        raise ValueError("run_id must not be empty")

    if not normalized_git_sha:
        raise ValueError("git_sha must not be empty")

    if not normalized_python:
        raise ValueError("python_version must not be empty")

    if not normalized_platform:
        raise ValueError(
            "platform_description must not be empty"
        )

    if not normalized_captured:
        raise ValueError(
            "captured_at_utc must not be empty"
        )

    validate_topology(nodes)

    return {
        "run_id": normalized_run_id,
        "git_sha": normalized_git_sha,
        "captured_at_utc": normalized_captured,
        "python_version": normalized_python,
        "platform": normalized_platform,
        "source": "measured-physical-runner",
        "cluster_size": len(nodes),
        "node_ids": [
            node.node_id
            for node in nodes
        ],
        "hub_url": str(hub_url),
        "authentication": "shared-secret-hmac",
        "transport_confidentiality": False,
        "external_anchor": {
            "configured": False,
            "reason": (
                "physical runner does not configure "
                "an external authenticated anchor"
            ),
        },
    }


def attach_provenance(
    evidence: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    result = dict(evidence)
    result["provenance"] = dict(provenance)
    return result


@dataclass
class ManagedProcess:
    process_id: str
    process: Any
    stdout_handle: Any = None
    stderr_handle: Any = None


def cleanup_managed_processes(
    managed: list[ManagedProcess],
    *,
    stopper: Any = stop_process,
    handle_closer: Any = close_process_handles,
) -> list[str]:
    errors: list[str] = []

    for item in reversed(managed):
        try:
            stopper(item.process)
        except Exception as exc:
            errors.append(
                f"{item.process_id}: stop failed: {exc}"
            )

        try:
            handle_closer(
                item.stdout_handle,
                item.stderr_handle,
            )
        except Exception as exc:
            errors.append(
                f"{item.process_id}: handle cleanup failed: {exc}"
            )

    return errors


def lifecycle_with_cleanup(
    *,
    body: Any,
    managed: list[ManagedProcess],
    stopper: Any = stop_process,
    handle_closer: Any = close_process_handles,
) -> Any:
    try:
        return body()
    finally:
        cleanup_managed_processes(
            managed,
            stopper=stopper,
            handle_closer=handle_closer,
        )

def baseline_from_hub_state(
    peers: dict[str, Any],
    *,
    expected_node_ids: set[str],
    expected_master_id: str,
) -> dict[str, Any] | None:
    """Return the canonical physical baseline or None.

    Axis 11 freezes the baseline semantics validated by the
    first valid physical reference sample (run-009).

    A baseline exists only when:
    - the Hub exposes exactly the expected node identities;
    - exactly one MASTER exists;
    - that MASTER is the expected initial master;
    - no Hub-level multiple-MASTER condition is present.

    Hub registry overlap after master termination is evaluated
    separately from operational split-brain.
    """

    if not isinstance(peers, dict):
        raise ValueError("peers must be a mapping")

    if not isinstance(expected_node_ids, set):
        raise ValueError(
            "expected_node_ids must be a set"
        )

    if not expected_node_ids:
        raise ValueError(
            "expected_node_ids must not be empty"
        )

    if any(
        not isinstance(node_id, str)
        or not node_id.strip()
        for node_id in expected_node_ids
    ):
        raise ValueError(
            "expected_node_ids must contain "
            "non-empty strings"
        )

    if (
        not isinstance(expected_master_id, str)
        or not expected_master_id.strip()
    ):
        raise ValueError(
            "expected_master_id must be non-empty"
        )

    if expected_master_id not in expected_node_ids:
        raise ValueError(
            "expected_master_id must belong to "
            "expected_node_ids"
        )

    state = observe_hub_state(
        peers,
        failed_master_id="__NONE__",
    )

    peer_ids = set(peers)

    if peer_ids != expected_node_ids:
        return None

    if state["masters"] != [expected_master_id]:
        return None

    if state["master_count"] != 1:
        return None

    if state["active_split_brain"] is not False:
        return None

    return {
        "peer_ids": sorted(peer_ids),
        "masters": list(state["masters"]),
        "master_count": state["master_count"],
        "active_split_brain": (
            state["active_split_brain"]
        ),
    }
