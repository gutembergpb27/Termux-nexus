"""Summarize pytest JUnit XML results for one CI test group.

Prints a table (and appends it to the GitHub step summary) with passed,
failed, errors, skipped, xfailed, and failures caused by the harness
memory gate (reported as BLOCKED; they still count as failures).

Exits 1 when a result file is missing, when any test failed or errored,
or when the number of executed tests differs from the expected count, so
a silently dropped test cannot pass unnoticed.

Usage: python junit_summary.py <group title> <expected count> <xml> [<xml> ...]
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BLOCKED_MARKERS = ("memory_pressure",)


def count(paths: list[Path]) -> tuple[dict[str, int], list[str]]:
    totals = dict.fromkeys(
        ("tests", "passed", "failed", "errors", "skipped", "xfailed", "blocked"), 0)
    problems = []
    for path in paths:
        if not path.is_file():
            problems.append(f"missing result file: {path.as_posix()}")
            continue
        for case in ET.parse(path).getroot().iter("testcase"):
            totals["tests"] += 1
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None or error is not None:
                node = failure if failure is not None else error
                text = f"{node.get('message', '')} {node.text or ''}"
                totals["failed" if failure is not None else "errors"] += 1
                if any(marker in text for marker in BLOCKED_MARKERS):
                    totals["blocked"] += 1
            elif skipped is not None:
                kind = "xfailed" if "xfail" in (skipped.get("type", "") or "") else "skipped"
                totals[kind] += 1
            else:
                totals["passed"] += 1
    return totals, problems


def main() -> int:
    title, expected, files = sys.argv[1], int(sys.argv[2]), [Path(p) for p in sys.argv[3:]]
    totals, problems = count(files)
    if totals["tests"] != expected:
        problems.append(f"executed {totals['tests']} tests, expected {expected}")
    if totals["failed"] or totals["errors"]:
        problems.append(f"{totals['failed']} failed, {totals['errors']} errors")
    verdict = "FAIL" if problems else "PASS"
    header = "| Tests | Passed | Failed | Errors | Skipped | XFailed | BLOCKED (memory gate) |"
    row = ("| {tests} | {passed} | {failed} | {errors} | {skipped} | {xfailed} | {blocked} |"
           .format(**totals))
    lines = [f"### {title}: {verdict}", "", header, "|---|---|---|---|---|---|---|", row, ""]
    lines += [f"- {p}" for p in problems]
    text = "\n".join(lines) + "\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
