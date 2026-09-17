"""
Nexus V2700 — Axis 10
Quorum timing benchmark.

Measurement clock:
    time.perf_counter()

Evidence clock:
    UTC ISO-8601

Metrics:
    M1 = T1 - T0
    M2 = T3 - T1
    M3 = T4 - T0

This runner contains no synthetic latency fallback.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


EVENTS = (
    "master_missing",
    "leadership_promotion_started",
    "leadership_promoted",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def measurement_point(name, start):
    now = time.perf_counter()

    return {
        "event": name,
        "monotonic_seconds": now,
        "elapsed_from_t0_seconds": now - start,
        "utc": utc_now(),
    }


def save_evidence(path, evidence):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            evidence,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def main():
    print("=" * 60)
    print("NEXUS V2700 — AXIS 10")
    print("QUORUM TIMING BENCHMARK")
    print("=" * 60)

    print()
    print("Measurement model:")
    print("T0 = controlled MASTER loss")
    print("T1 = master_missing")
    print("T2 = leadership_promotion_started")
    print("T3 = leadership_promoted")
    print("T4 = externally observed MASTER")
    print()
    print("M1 = T1 - T0")
    print("M2 = T3 - T1")
    print("M3 = T4 - T0")
    print()
    print("Clock = time.perf_counter()")
    print("Synthetic latency fallback = NONE")
    print()

    # This phase establishes the measurement harness only.
    # Process orchestration is deliberately added after its
    # exact startup/shutdown commands are certified.

    start = time.perf_counter()

    evidence = {
        "axis": 10,
        "benchmark": "quorum-timing",
        "clock": "time.perf_counter",
        "created_utc": utc_now(),
        "measurement_model": {
            "T0": "controlled MASTER loss",
            "T1": "master_missing",
            "T2": "leadership_promotion_started",
            "T3": "leadership_promoted",
            "T4": "externally observed MASTER",
            "M1": "T1-T0",
            "M2": "T3-T1",
            "M3": "T4-T0",
        },
        "synthetic_latency_fallback": False,
        "harness_initialized": measurement_point(
            "harness_initialized",
            start,
        ),
    }

    save_evidence(
        "validation/quorum-timing/harness-evidence.json",
        evidence,
    )

    print("HARNESS = INITIALIZED")
    print(
        "Evidence = "
        "validation/quorum-timing/harness-evidence.json"
    )


if __name__ == "__main__":
    main()