from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "validation"
    / "statistical-resilience"
    / "campaign_runner.py"
)

SPEC = importlib.util.spec_from_file_location(
    "axis11_campaign_runner",
    MODULE_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

campaign_runner = importlib.util.module_from_spec(
    SPEC
)

sys.modules[SPEC.name] = campaign_runner
SPEC.loader.exec_module(campaign_runner)


def test_campaign_plan_produces_exact_run_ids():
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=30,
    )

    assert len(plan.run_ids) == 30
    assert plan.run_ids[0] == "run-010"
    assert plan.run_ids[-1] == "run-039"
    assert len(set(plan.run_ids)) == 30


def test_campaign_plan_rejects_invalid_values():
    with pytest.raises(ValueError):
        campaign_runner.CampaignPlan(
            start_run=0,
            sample_count=30,
        )

    with pytest.raises(ValueError):
        campaign_runner.CampaignPlan(
            start_run=10,
            sample_count=0,
        )


def test_discover_run_ids_is_numeric_and_deterministic(
    tmp_path,
):
    for name in (
        "run-009",
        "run-002",
        "run-010",
        "not-a-run",
    ):
        (tmp_path / name).mkdir()

    assert campaign_runner.discover_run_ids(
        tmp_path
    ) == (
        "run-002",
        "run-009",
        "run-010",
    )


def test_assert_plan_is_fresh_rejects_collision(
    tmp_path,
):
    (tmp_path / "run-011").mkdir()

    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=3,
    )

    with pytest.raises(
        FileExistsError,
        match="run-011",
    ):
        campaign_runner.assert_plan_is_fresh(
            tmp_path,
            plan,
        )


def test_manifest_preserves_methodology_identity():
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=2,
    )

    manifest = (
        campaign_runner.build_campaign_manifest(
            plan=plan,
            methodology_git_sha="abc123",
            reference_run_id="run-009",
            reference_run_sha256="deadbeef",
        )
    )

    assert manifest == {
        "schema": (
            "nexus.axis11.physical-campaign.v1"
        ),
        "methodology_git_sha": "abc123",
        "reference": {
            "run_id": "run-009",
            "sha256": "deadbeef",
        },
        "start_run": 10,
        "sample_count": 2,
        "run_ids": [
            "run-010",
            "run-011",
        ],
        "preserve_invalid_runs": True,
        "overwrite_existing_runs": False,
    }


def test_save_manifest_is_deterministic(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    manifest = {
        "z": 1,
        "a": 2,
    }

    campaign_runner.save_manifest(
        path,
        manifest,
    )

    first = path.read_bytes()

    campaign_runner.save_manifest(
        path,
        manifest,
    )

    second = path.read_bytes()

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first) == manifest


def test_load_run_summaries_preserves_order(
    tmp_path,
):
    for run_id, value in (
        ("run-010", 10),
        ("run-011", 11),
    ):
        directory = tmp_path / run_id
        directory.mkdir()

        (
            directory
            / "benchmark-summary.json"
        ).write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "value": value,
                }
            ),
            encoding="utf-8",
        )

    records = (
        campaign_runner.load_run_summaries(
            tmp_path,
            (
                "run-011",
                "run-010",
            ),
        )
    )

    assert [
        record["run_id"]
        for record in records
    ] == [
        "run-011",
        "run-010",
    ]


def test_load_run_summaries_rejects_missing(
    tmp_path,
):
    with pytest.raises(
        FileNotFoundError,
        match="run-010",
    ):
        campaign_runner.load_run_summaries(
            tmp_path,
            ("run-010",),
        )

def _write_complete_run(
    root,
    run_id,
):
    directory = root / run_id
    directory.mkdir()

    (
        directory
        / "benchmark-summary.json"
    ).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "classification": "valid",
            }
        ),
        encoding="utf-8",
    )


def test_next_campaign_run_id_uses_first_fresh_run(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=3,
    )

    _write_complete_run(
        tmp_path,
        "run-010",
    )

    assert campaign_runner.next_campaign_run_id(
        evidence_root=tmp_path,
        plan=plan,
    ) == "run-011"


def test_next_campaign_run_id_returns_none_when_complete(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=2,
    )

    _write_complete_run(tmp_path, "run-010")
    _write_complete_run(tmp_path, "run-011")

    assert campaign_runner.next_campaign_run_id(
        evidence_root=tmp_path,
        plan=plan,
    ) is None


def test_assert_run_belongs_to_plan():
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=2,
    )

    campaign_runner.assert_run_belongs_to_plan(
        "run-010",
        plan,
    )

    with pytest.raises(
        ValueError,
        match="outside campaign plan",
    ):
        campaign_runner.assert_run_belongs_to_plan(
            "run-009",
            plan,
        )


def test_campaign_progress_counts_immutable_runs(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=3,
    )

    _write_complete_run(tmp_path, "run-010")

    progress = campaign_runner.campaign_progress(
        evidence_root=tmp_path,
        plan=plan,
    )

    assert progress["planned"] == 3
    assert progress["completed"] == 1
    assert progress["pending"] == 2
    assert progress["completed_run_ids"] == [
        "run-010",
    ]
    assert progress["pending_run_ids"] == [
        "run-011",
        "run-012",
    ]
    assert progress["next_run_id"] == "run-011"


def test_validate_completed_prefix_accepts_ordered_runs(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=3,
    )

    _write_complete_run(tmp_path, "run-010")
    _write_complete_run(tmp_path, "run-011")

    assert campaign_runner.validate_completed_prefix(
        evidence_root=tmp_path,
        plan=plan,
    ) == (
        "run-010",
        "run-011",
    )


def test_validate_completed_prefix_rejects_hole(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=3,
    )

    _write_complete_run(tmp_path, "run-011")

    with pytest.raises(
        RuntimeError,
        match="run-order hole",
    ):
        campaign_runner.validate_completed_prefix(
            evidence_root=tmp_path,
            plan=plan,
        )


def test_validate_completed_prefix_rejects_incomplete_run(
    tmp_path,
):
    plan = campaign_runner.CampaignPlan(
        start_run=10,
        sample_count=2,
    )

    (tmp_path / "run-010").mkdir()

    with pytest.raises(
        FileNotFoundError,
        match="run-010",
    ):
        campaign_runner.validate_completed_prefix(
            evidence_root=tmp_path,
            plan=plan,
        )
