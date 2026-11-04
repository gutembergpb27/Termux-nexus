"""Memory pre-check before the S1/S5 harness orchestration tests.

Uses the harness's own measurement (available_memory_mb) and its own floor
(MIN_FREE_MB_FLOOR, 2048 MB). It never lowers the floor. With less memory
the orchestration tests could end in BLOCKED memory_pressure (floor
512 MB during a run), so this check reports BLOCKED and exits 3, which
fails the CI step instead of letting those tests run on a starved host.

Usage: python ci_memory_check.py <path to s1s5_harness.py>
"""

import importlib.util
import os
import sys
from pathlib import Path

EXIT_BLOCKED = 3


def load_harness(path: Path):
    spec = importlib.util.spec_from_file_location("s1s5_harness", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1s5_harness"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    harness = load_harness(Path(sys.argv[1]).resolve())
    floor = harness.MIN_FREE_MB_FLOOR
    run_floor = harness.MEMORY_PRESSURE_FLOOR_MB
    available = harness.available_memory_mb()
    if available is None:
        status, detail = "BLOCKED", "free memory could not be measured"
    elif available < floor:
        status, detail = "BLOCKED", f"{available:.0f} MB free < {floor} MB required"
    else:
        status, detail = "PASS", f"{available:.0f} MB free >= {floor} MB required"
    line = (f"Memory pre-check: {status}: {detail} "
            f"(harness aborts a run below {run_floor} MB)")
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"- {line}\n")
    return 0 if status == "PASS" else EXIT_BLOCKED


if __name__ == "__main__":
    sys.exit(main())
