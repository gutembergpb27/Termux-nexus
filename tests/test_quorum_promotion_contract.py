from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "nexus_distributed_core.py"
)


def _source() -> str:
    return SOURCE_PATH.read_text(
        encoding="utf-8"
    )


def _promotion_window(source: str) -> str:
    """
    Return the failover code between deterministic candidate
    selection and the actual assignment of MASTER authority.

    Axis 8 Contract 1 requires an explicit quorum/majority
    authorization gate inside this window.
    """

    candidate = source.index(
        "promotion_candidate = max("
    )

    promotion = source.index(
        'self.role = "MASTER"',
        candidate,
    )

    return source[candidate:promotion]


def test_master_promotion_requires_explicit_quorum_gate():
    """
    Missing MASTER plus deterministic candidate selection is
    not sufficient authority to promote.

    Before assigning MASTER, the runtime must contain an
    explicit quorum/majority authorization decision.
    """

    source = _source()
    window = _promotion_window(source).lower()

    assert (
        "quorum" in window
        or "majority" in window
    ), (
        "Axis 8 Contract 1 violated: deterministic candidate "
        "selection exists, but MASTER promotion is not gated "
        "by explicit quorum/majority evidence"
    )


def test_quorum_gate_occurs_before_master_assignment():
    """
    Any quorum/majority gate must occur after candidate
    selection and before MASTER authority is assigned.
    """

    source = _source()
    lower = source.lower()

    candidate = source.index(
        "promotion_candidate = max("
    )

    promotion = source.index(
        'self.role = "MASTER"',
        candidate,
    )

    positions = []

    for marker in (
        "quorum",
        "majority",
    ):
        position = lower.find(
            marker,
            candidate,
            promotion,
        )

        if position != -1:
            positions.append(position)

    assert positions, (
        "Axis 8 Contract 1 violated: no quorum/majority gate "
        "exists between candidate selection and MASTER "
        "assignment"
    )

    assert min(positions) < promotion
