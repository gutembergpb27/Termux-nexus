from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

CAMPAIGN_SCHEMA = "nexus.axis11.physical-campaign.v1"
RUN_DIRECTORY_PATTERN = re.compile(r"^run-(\d{3,})$")


@dataclass(frozen=True)
class CampaignPlan:
    start_run: int
    sample_count: int

    def __post_init__(self) -> None:
        if self.start_run < 1:
            raise ValueError("start_run must be >= 1")
        if self.sample_count < 1:
            raise ValueError("sample_count must be >= 1")

    @property
    def run_ids(self) -> tuple[str, ...]:
        stop = self.start_run + self.sample_count
        return tuple(
            f"run-{number:03d}"
            for number in range(self.start_run, stop)
        )


def discover_run_ids(
    evidence_root: str | pathlib.Path,
) -> tuple[str, ...]:
    root = pathlib.Path(evidence_root)

    if not root.exists():
        return ()

    discovered: list[tuple[int, str]] = []

    for child in root.iterdir():
        if not child.is_dir():
            continue

        match = RUN_DIRECTORY_PATTERN.fullmatch(
            child.name
        )

        if match is None:
            continue

        discovered.append(
            (int(match.group(1)), child.name)
        )

    discovered.sort()

    return tuple(
        run_id for _, run_id in discovered
    )


def assert_plan_is_fresh(
    evidence_root: str | pathlib.Path,
    plan: CampaignPlan,
) -> None:
    root = pathlib.Path(evidence_root)

    collisions = [
        run_id
        for run_id in plan.run_ids
        if (root / run_id).exists()
    ]

    if collisions:
        raise FileExistsError(
            "campaign run directories already exist: "
            + ", ".join(collisions)
        )


def build_campaign_manifest(
    *,
    plan: CampaignPlan,
    methodology_git_sha: str,
    reference_run_id: str,
    reference_run_sha256: str,
) -> dict[str, Any]:
    if not methodology_git_sha.strip():
        raise ValueError(
            "methodology_git_sha must not be empty"
        )

    if not reference_run_id.strip():
        raise ValueError(
            "reference_run_id must not be empty"
        )

    if not reference_run_sha256.strip():
        raise ValueError(
            "reference_run_sha256 must not be empty"
        )

    return {
        "schema": CAMPAIGN_SCHEMA,
        "methodology_git_sha": methodology_git_sha,
        "reference": {
            "run_id": reference_run_id,
            "sha256": reference_run_sha256,
        },
        "start_run": plan.start_run,
        "sample_count": plan.sample_count,
        "run_ids": list(plan.run_ids),
        "preserve_invalid_runs": True,
        "overwrite_existing_runs": False,
    }


def save_manifest(
    path: str | pathlib.Path,
    manifest: dict[str, Any],
) -> pathlib.Path:
    target = pathlib.Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )

    target.write_text(
        payload + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return target


def load_run_summaries(
    evidence_root: str | pathlib.Path,
    run_ids: Iterable[str],
) -> list[dict[str, Any]]:
    root = pathlib.Path(evidence_root)
    records: list[dict[str, Any]] = []

    for run_id in run_ids:
        path = (
            root
            / run_id
            / "benchmark-summary.json"
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"missing summary for {run_id}: {path}"
            )

        record = json.loads(
            path.read_text(encoding="utf-8")
        )

        records.append(record)

    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Nexus Axis 11 physical statistical "
            "campaign planner."
        )
    )

    parser.add_argument(
        "--evidence-root",
        default=(
            "validation/statistical-resilience/"
            "evidence"
        ),
    )

    parser.add_argument(
        "--start-run",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--methodology-git-sha",
        required=True,
    )

    parser.add_argument(
        "--reference-run",
        default="run-009",
    )

    parser.add_argument(
        "--reference-sha256",
        required=True,
    )

    parser.add_argument(
        "--manifest",
        default=None,
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help=(
            "Validate and emit the campaign plan. "
            "No physical process is started."
        ),
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    root = pathlib.Path(args.evidence_root)

    plan = CampaignPlan(
        start_run=args.start_run,
        sample_count=args.samples,
    )

    assert_plan_is_fresh(
        root,
        plan,
    )

    manifest = build_campaign_manifest(
        plan=plan,
        methodology_git_sha=(
            args.methodology_git_sha
        ),
        reference_run_id=args.reference_run,
        reference_run_sha256=(
            args.reference_sha256
        ),
    )

    if args.manifest is not None:
        save_manifest(
            args.manifest,
            manifest,
        )

    print(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
    )

    if args.plan_only:
        return 0

    raise RuntimeError(
        "Physical campaign execution is intentionally "
        "disabled until the executor freeze checkpoint."
    )


if __name__ == "__main__":
    raise SystemExit(main())

def next_campaign_run_id(
    *,
    evidence_root: str | pathlib.Path,
    plan: CampaignPlan,
) -> str | None:
    """Return the first not-yet-created run in the campaign.

    Existing run directories are immutable. Invalid runs count
    as consumed samples and are never silently retried.
    """
    root = pathlib.Path(evidence_root)

    for run_id in plan.run_ids:
        if not (root / run_id).exists():
            return run_id

    return None


def assert_run_belongs_to_plan(
    run_id: str,
    plan: CampaignPlan,
) -> None:
    if run_id not in plan.run_ids:
        raise ValueError(
            f"run_id is outside campaign plan: {run_id}"
        )


def campaign_progress(
    *,
    evidence_root: str | pathlib.Path,
    plan: CampaignPlan,
) -> dict[str, Any]:
    root = pathlib.Path(evidence_root)

    completed = [
        run_id
        for run_id in plan.run_ids
        if (root / run_id).is_dir()
    ]

    pending = [
        run_id
        for run_id in plan.run_ids
        if not (root / run_id).exists()
    ]

    return {
        "planned": len(plan.run_ids),
        "completed": len(completed),
        "pending": len(pending),
        "completed_run_ids": completed,
        "pending_run_ids": pending,
        "next_run_id": (
            pending[0] if pending else None
        ),
    }


def require_complete_run_summary(
    evidence_root: str | pathlib.Path,
    run_id: str,
) -> pathlib.Path:
    path = (
        pathlib.Path(evidence_root)
        / run_id
        / "benchmark-summary.json"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"immutable run lacks benchmark summary: {run_id}"
        )

    return path


def validate_completed_prefix(
    *,
    evidence_root: str | pathlib.Path,
    plan: CampaignPlan,
) -> tuple[str, ...]:
    """Reject holes and incomplete immutable runs.

    Campaign execution must progress strictly in plan order:
    run-010, run-011, ... . Once a directory exists, its
    benchmark summary must exist as well.
    """
    root = pathlib.Path(evidence_root)
    completed: list[str] = []
    encountered_pending = False

    for run_id in plan.run_ids:
        directory = root / run_id

        if directory.exists():
            if encountered_pending:
                raise RuntimeError(
                    "campaign contains a run-order hole at "
                    f"{run_id}"
                )

            require_complete_run_summary(
                root,
                run_id,
            )
            completed.append(run_id)
        else:
            encountered_pending = True

    return tuple(completed)
