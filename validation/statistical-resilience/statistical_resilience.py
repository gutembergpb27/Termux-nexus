"""
Nexus V2700 — Axis 11
Statistical Resilience Benchmarking.

Statistical aggregation for measured distributed failover runs.

This module:
- does not orchestrate cluster failures;
- does not generate synthetic latency;
- preserves invalid runs in campaign accounting;
- uses only valid runs for latency distributions.
"""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


SCHEMA = "nexus.axis11.statistical-resilience.v1"
RUN_SCHEMA = "nexus.axis11.statistical-resilience.run.v1"

TIMING_FIELDS = (
    "t0_to_t1",
    "t1_to_t3",
    "t3_to_t4",
    "t0_to_t4",
)


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    """Return a linearly interpolated percentile."""
    if not values:
        raise ValueError("values must not be empty")

    if not 0 <= percentile_value <= 100:
        raise ValueError(
            "percentile must be between 0 and 100"
        )

    ordered = sorted(float(value) for value in values)

    rank = (
        (len(ordered) - 1)
        * (percentile_value / 100.0)
    )

    lower = math.floor(rank)
    upper = math.ceil(rank)

    if lower == upper:
        return ordered[lower]

    weight = rank - lower

    return (
        ordered[lower] * (1.0 - weight)
        + ordered[upper] * weight
    )


def summarize(samples_ms: Iterable[float]) -> dict[str, Any]:
    """Summarize measured latency samples in milliseconds."""
    samples = [float(value) for value in samples_ms]

    if not samples:
        raise ValueError("at least one sample is required")

    if any(not math.isfinite(value) for value in samples):
        raise ValueError("samples must be finite")

    if any(value < 0 for value in samples):
        raise ValueError("samples must be non-negative")

    return {
        "schema": SCHEMA,
        "unit": "milliseconds",
        "count": len(samples),
        "min": min(samples),
        "max": max(samples),
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "stddev": (
            statistics.stdev(samples)
            if len(samples) > 1
            else 0.0
        ),
        "p50": percentile(samples, 50),
        "p90": percentile(samples, 90),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
    }


def _finite_non_negative(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be numeric"
        ) from exc

    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")

    if result < 0:
        raise ValueError(
            f"{field} must be non-negative"
        )

    return result


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")

    return value


def validate_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one Axis 11 run record."""
    required = (
        "run_id",
        "classification",
        "experiment",
        "timing_ms",
        "promoted_node",
        "converged",
        "active_split_brain_observed",
    )

    missing = [
        field
        for field in required
        if field not in run
    ]

    if missing:
        raise ValueError(
            "missing run fields: " + ", ".join(missing)
        )

    run_id = str(run["run_id"]).strip()
    experiment = str(run["experiment"]).strip()

    if not run_id:
        raise ValueError("run_id must not be empty")

    if not experiment:
        raise ValueError("experiment must not be empty")

    classification = str(run["classification"])

    if classification not in {"valid", "invalid"}:
        raise ValueError(
            "classification must be valid or invalid"
        )

    timing = run["timing_ms"]

    if not isinstance(timing, Mapping):
        raise ValueError("timing_ms must be a mapping")

    normalized_timing: dict[str, float] = {}

    if classification == "valid":
        for field in TIMING_FIELDS:
            if field not in timing:
                raise ValueError(
                    f"missing timing field: {field}"
                )

            normalized_timing[field] = (
                _finite_non_negative(
                    timing[field],
                    f"timing_ms.{field}",
                )
            )
    else:
        for field in TIMING_FIELDS:
            if field not in timing:
                continue

            normalized_timing[field] = (
                _finite_non_negative(
                    timing[field],
                    f"timing_ms.{field}",
                )
            )

    converged = _strict_bool(
        run["converged"],
        "converged",
    )

    split_brain = _strict_bool(
        run["active_split_brain_observed"],
        "active_split_brain_observed",
    )

    promoted_raw = run["promoted_node"]

    if promoted_raw is None:
        promoted_node = None
    elif isinstance(promoted_raw, str):
        promoted_node = promoted_raw.strip() or None
    else:
        raise ValueError(
            "promoted_node must be a string or None"
        )

    invalid_reason_raw = run.get("invalid_reason")

    if invalid_reason_raw is None:
        invalid_reason = None
    elif isinstance(invalid_reason_raw, str):
        invalid_reason = invalid_reason_raw.strip() or None
    else:
        raise ValueError(
            "invalid_reason must be a string or None"
        )

    if classification == "valid":
        if promoted_node is None:
            raise ValueError(
                "valid run requires promoted_node"
            )

        if invalid_reason is not None:
            raise ValueError(
                "valid run must not have invalid_reason"
            )
    else:
        if invalid_reason is None:
            raise ValueError(
                "invalid run requires invalid_reason"
            )

    environment = run.get("environment")
    provenance = run.get("provenance")

    if environment is not None and not isinstance(
        environment,
        Mapping,
    ):
        raise ValueError(
            "environment must be a mapping"
        )

    if provenance is not None and not isinstance(
        provenance,
        Mapping,
    ):
        raise ValueError(
            "provenance must be a mapping"
        )

    return {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "classification": classification,
        "experiment": experiment,
        "timing_ms": normalized_timing,
        "promoted_node": promoted_node,
        "converged": converged,
        "active_split_brain_observed": split_brain,
        "invalid_reason": invalid_reason,
        "environment": (
            dict(environment)
            if environment is not None
            else {}
        ),
        "provenance": (
            dict(provenance)
            if provenance is not None
            else {}
        ),
    }

def summarize_campaign(
    runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate a campaign of measured failover runs."""
    normalized = [
        validate_run(run)
        for run in runs
    ]

    if not normalized:
        raise ValueError(
            "at least one run is required"
        )

    run_ids = [run["run_id"] for run in normalized]

    if len(run_ids) != len(set(run_ids)):
        raise ValueError("run_id values must be unique")

    valid = [
        run
        for run in normalized
        if run["classification"] == "valid"
    ]

    invalid = [
        run
        for run in normalized
        if run["classification"] == "invalid"
    ]

    if not valid:
        raise ValueError(
            "campaign requires at least one valid run"
        )

    experiments = {
        run["experiment"]
        for run in normalized
    }

    if len(experiments) != 1:
        raise ValueError(
            "campaign runs must share one experiment"
        )

    timing_statistics = {}

    for field in TIMING_FIELDS:
        timing_statistics[field] = summarize(
            run["timing_ms"][field]
            for run in valid
        )

    split_brain_count = sum(
        1
        for run in normalized
        if run["active_split_brain_observed"]
    )

    convergence_count = sum(
        1
        for run in normalized
        if run["converged"]
    )

    promoted_nodes: dict[str, int] = {}

    for run in valid:
        node = run["promoted_node"]

        promoted_nodes[node] = (
            promoted_nodes.get(node, 0) + 1
        )

    return {
        "schema": SCHEMA,
        "experiment": valid[0]["experiment"],
        "runs": {
            "total": len(normalized),
            "valid": len(valid),
            "invalid": len(invalid),
        },
        "timing_statistics_ms": timing_statistics,
        "convergence": {
            "count": convergence_count,
            "rate": (
                convergence_count / len(normalized)
            ),
        },
        "active_split_brain": {
            "count": split_brain_count,
            "observed": split_brain_count > 0,
        },
        "promoted_nodes": promoted_nodes,
    }

def save_json_evidence(
    path: str | Path,
    evidence: Mapping[str, Any],
) -> None:
    """Persist evidence as deterministic UTF-8 JSON."""
    destination = Path(path)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        json.dumps(
            dict(evidence),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
