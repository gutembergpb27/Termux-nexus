import importlib.util
import math
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "statistical-resilience"
    / "statistical_resilience.py"
)

SPEC = importlib.util.spec_from_file_location(
    "nexus_statistical_resilience",
    MODULE_PATH,
)

module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def make_run(
    run_id,
    total,
    *,
    classification="valid",
    promoted_node="NODE-C",
    converged=True,
    split_brain=False,
):
    run = {
        "run_id": run_id,
        "classification": classification,
        "experiment": (
            "three-node-master-loss-failover"
        ),
        "timing_ms": {
            "t0_to_t1": total * 0.75,
            "t1_to_t3": total * 0.05,
            "t3_to_t4": total * 0.20,
            "t0_to_t4": total,
        },
        "promoted_node": promoted_node,
        "converged": converged,
        "active_split_brain_observed": split_brain,
    }

    if classification == "invalid":
        run["invalid_reason"] = "controlled invalid test run"

    return run


def test_schema_identity():
    assert module.SCHEMA == (
        "nexus.axis11.statistical-resilience.v1"
    )

    assert module.RUN_SCHEMA == (
        "nexus.axis11.statistical-resilience.run.v1"
    )


def test_percentile_single_sample():
    assert module.percentile([24.0], 99) == 24.0


def test_percentile_boundaries():
    samples = [10.0, 20.0, 30.0, 40.0]

    assert module.percentile(samples, 0) == 10.0
    assert module.percentile(samples, 100) == 40.0


def test_summary_contract():
    result = module.summarize(
        [10.0, 20.0, 30.0, 40.0, 50.0]
    )

    assert result["count"] == 5
    assert result["min"] == 10.0
    assert result["max"] == 50.0
    assert result["mean"] == 30.0
    assert result["median"] == 30.0
    assert result["stddev"] > 0
    assert result["p50"] == 30.0
    assert result["p99"] >= result["p95"]


def test_summary_single_sample():
    result = module.summarize([24209.728])

    assert result["count"] == 1
    assert result["stddev"] == 0.0
    assert result["p50"] == 24209.728
    assert result["p99"] == 24209.728


@pytest.mark.parametrize(
    "samples",
    [
        [],
        [-1.0],
        [math.nan],
        [math.inf],
        [-math.inf],
    ],
)
def test_invalid_samples_are_rejected(samples):
    with pytest.raises(ValueError):
        module.summarize(samples)


def test_invalid_percentile_is_rejected():
    with pytest.raises(ValueError):
        module.percentile([1.0], -1)

    with pytest.raises(ValueError):
        module.percentile([1.0], 101)


def test_validate_run_contract():
    result = module.validate_run(
        make_run("run-001", 24000.0)
    )

    assert result["run_id"] == "run-001"
    assert result["classification"] == "valid"
    assert result["timing_ms"]["t0_to_t4"] == 24000.0


def test_campaign_statistics():
    result = module.summarize_campaign(
        [
            make_run("run-001", 20000.0),
            make_run("run-002", 24000.0),
            make_run("run-003", 28000.0),
        ]
    )

    assert result["runs"] == {
        "total": 3,
        "valid": 3,
        "invalid": 0,
    }

    total = result["timing_statistics_ms"]["t0_to_t4"]

    assert total["count"] == 3
    assert total["min"] == 20000.0
    assert total["max"] == 28000.0
    assert total["median"] == 24000.0

    assert result["convergence"]["rate"] == 1.0

    assert result["active_split_brain"] == {
        "count": 0,
        "observed": False,
    }

    assert result["promoted_nodes"] == {
        "NODE-C": 3
    }


def test_invalid_run_excluded_from_latency_distribution():
    result = module.summarize_campaign(
        [
            make_run("run-001", 20000.0),
            make_run(
                "run-002",
                90000.0,
                classification="invalid",
                converged=False,
            ),
        ]
    )

    assert result["runs"]["total"] == 2
    assert result["runs"]["valid"] == 1
    assert result["runs"]["invalid"] == 1

    total = result["timing_statistics_ms"]["t0_to_t4"]

    assert total["count"] == 1
    assert total["mean"] == 20000.0


def test_duplicate_run_ids_rejected():
    with pytest.raises(ValueError):
        module.summarize_campaign(
            [
                make_run("run-001", 20000.0),
                make_run("run-001", 21000.0),
            ]
        )


def test_campaign_requires_valid_run():
    with pytest.raises(ValueError):
        module.summarize_campaign(
            [
                make_run(
                    "run-001",
                    20000.0,
                    classification="invalid",
                )
            ]
        )


def test_missing_timing_field_rejected():
    run = make_run("run-001", 20000.0)

    del run["timing_ms"]["t3_to_t4"]

    with pytest.raises(ValueError):
        module.validate_run(run)

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("converged", "false"),
        ("converged", 1),
        ("active_split_brain_observed", "false"),
        ("active_split_brain_observed", 0),
    ],
)
def test_run_boolean_fields_are_strict(field, value):
    run = make_run("run-001", 20000.0)
    run[field] = value

    with pytest.raises(ValueError):
        module.validate_run(run)


def test_campaign_rejects_mixed_experiments():
    first = make_run("run-001", 20000.0)
    second = make_run("run-002", 21000.0)

    second["experiment"] = (
        "different-failover-experiment"
    )

    with pytest.raises(ValueError):
        module.summarize_campaign(
            [first, second]
        )

def test_run_preserves_environment_and_provenance():
    run = make_run("run-001", 20000.0)

    run["environment"] = {
        "platform": "Windows",
        "python": "3.14.6",
        "cluster_size": 3,
    }

    run["provenance"] = {
        "git_sha": "abc123",
        "source": "measured",
    }

    result = module.validate_run(run)

    assert result["environment"]["cluster_size"] == 3
    assert result["provenance"]["source"] == "measured"
    assert result["provenance"]["git_sha"] == "abc123"


@pytest.mark.parametrize(
    "field",
    [
        "environment",
        "provenance",
    ],
)
def test_evidence_metadata_must_be_mapping(field):
    run = make_run("run-001", 20000.0)
    run[field] = "invalid"

    with pytest.raises(ValueError):
        module.validate_run(run)


def test_evidence_metadata_defaults_to_empty_mapping():
    result = module.validate_run(
        make_run("run-001", 20000.0)
    )

    assert result["environment"] == {}
    assert result["provenance"] == {}


def test_save_json_evidence_is_deterministic(tmp_path):
    path = tmp_path / "evidence" / "run.json"

    evidence = {
        "z": 3,
        "a": 1,
        "nested": {
            "b": 2,
            "a": 1,
        },
    }

    module.save_json_evidence(
        path,
        evidence,
    )

    first = path.read_bytes()

    module.save_json_evidence(
        path,
        evidence,
    )

    second = path.read_bytes()

    assert first == second
    assert first.startswith(b"{\n")
    assert first.endswith(b"\n")
    assert b'"a": 1' in first
    assert first.find(b'"a": 1') < first.find(b'"z": 3')


def test_save_json_evidence_uses_utf8(tmp_path):
    path = tmp_path / "run.json"

    module.save_json_evidence(
        path,
        {
            "description": "resili?ncia",
        },
    )

    raw = path.read_bytes()

    assert raw.startswith(b"{")
    assert not raw.startswith(b"\xef\xbb\xbf")

    decoded = raw.decode("utf-8")

    assert "resili?ncia" in decoded
def test_invalid_run_preserves_partial_timing():
    run = make_run(
        "run-partial",
        20000.0,
        classification="invalid",
        promoted_node=None,
        converged=False,
    )

    run["timing_ms"] = {
        "t0_to_t1": 15000.0,
    }
    run["invalid_reason"] = "timeout before promotion"

    result = module.validate_run(run)

    assert result["classification"] == "invalid"
    assert result["timing_ms"] == {
        "t0_to_t1": 15000.0,
    }
    assert result["promoted_node"] is None
    assert result["invalid_reason"] == (
        "timeout before promotion"
    )


def test_invalid_run_requires_reason():
    run = make_run(
        "run-invalid",
        20000.0,
        classification="invalid",
        converged=False,
    )

    del run["invalid_reason"]

    with pytest.raises(
        ValueError,
        match="invalid run requires invalid_reason",
    ):
        module.validate_run(run)


def test_valid_run_still_requires_all_canonical_timings():
    run = make_run("run-valid", 20000.0)

    del run["timing_ms"]["t1_to_t3"]

    with pytest.raises(
        ValueError,
        match="missing timing field: t1_to_t3",
    ):
        module.validate_run(run)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", ""),
        ("run_id", "   "),
        ("experiment", ""),
        ("experiment", "   "),
    ],
)
def test_run_identity_fields_must_be_non_empty(field, value):
    run = make_run("run-identity", 20000.0)
    run[field] = value

    with pytest.raises(ValueError):
        module.validate_run(run)


def test_valid_run_requires_promoted_node():
    run = make_run(
        "run-no-promotion",
        20000.0,
        promoted_node=None,
    )

    with pytest.raises(
        ValueError,
        match="valid run requires promoted_node",
    ):
        module.validate_run(run)


def test_valid_run_rejects_invalid_reason():
    run = make_run("run-valid-reason", 20000.0)
    run["invalid_reason"] = "must not exist"

    with pytest.raises(
        ValueError,
        match="valid run must not have invalid_reason",
    ):
        module.validate_run(run)
