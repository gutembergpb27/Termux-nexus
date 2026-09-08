from pathlib import Path


CORE_PATH = Path("nexus_distributed_core.py")


def polling_source():
    source = CORE_PATH.read_text(
        encoding="utf-8-sig"
    )

    start = source.index(
        "    def async_polling_loop(self):"
    )

    end = source.index(
        "    def shell_intake_loop(self):",
        start,
    )

    return source[start:end]


def test_promotion_requires_deterministic_candidate_selection():
    """
    Axis 6 contract.

    Detection of a missing/unreachable MASTER is not by itself
    sufficient authority for every FOLLOWER to promote.

    Before assigning MASTER, the polling failover path must
    deterministically select an eligible promotion candidate.
    """

    source = polling_source()

    promotion = source.index(
        'self.role = "MASTER"'
    )

    candidate_markers = (
        "promotion_candidate",
        "eligible_candidate",
        "candidate_node",
    )

    positions = [
        source.find(marker)
        for marker in candidate_markers
        if source.find(marker) != -1
    ]

    assert positions, (
        "FOLLOWER promotes directly to MASTER without "
        "deterministic candidate selection"
    )

    assert min(positions) < promotion, (
        "promotion candidate selection must occur before "
        'self.role = "MASTER"'
    )


def test_promotion_candidate_rule_is_deterministic():
    """
    Concurrent followers must derive the same winner from
    the same peer view.

    Axis 6 initially adopts the existing Nexus ordering
    invariant: lexicographically greatest stable node_id wins.
    """

    source = polling_source()

    assert (
        "max(" in source
        or "sorted(" in source
    ), (
        "polling failover path has no deterministic "
        "candidate ordering before promotion"
    )


def test_promotion_is_not_authorized_by_timeout_alone():
    """
    Timeout establishes MASTER unreachability.

    It must not, by itself, authorize every follower to
    mutate its role directly to MASTER.
    """

    source = polling_source()

    timeout = source.index(
        "delta > 15.0"
    )

    promotion = source.index(
        'self.role = "MASTER"',
        timeout,
    )

    between = source[timeout:promotion]

    assert (
        "promotion_candidate" in between
        or "eligible_candidate" in between
        or "candidate_node" in between
    ), (
        "timeout currently leads directly to MASTER "
        "promotion without candidate authorization"
    )
