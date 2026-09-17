import inspect

import nexus_distributed_core


def _runtime_class():
    matches = []

    for obj in vars(nexus_distributed_core).values():
        if not inspect.isclass(obj):
            continue

        if obj.__module__ != nexus_distributed_core.__name__:
            continue

        try:
            source = inspect.getsource(obj)
        except (OSError, TypeError):
            continue

        if (
            "promotion_candidate = max(" in source
            and 'self.role = "MASTER"' in source
        ):
            matches.append(obj)

    assert len(matches) == 1, (
        "Axis 8 test invariant violated: expected exactly "
        "one runtime class containing promotion logic"
    )

    return matches[0]


def _source():
    return inspect.getsource(
        _runtime_class()
    )


def test_runtime_declares_stable_cluster_size_configuration():
    """
    Axis 8 requires quorum authority to be derived from
    stable configured membership, not merely the currently
    visible peer set.
    """

    source = _source()

    assert "NEXUS_CLUSTER_SIZE" in source, (
        "Axis 8 Contract 1A violated: runtime has no stable "
        "cluster-size configuration"
    )

    assert "configured_cluster_size" in source, (
        "Axis 8 Contract 1A violated: configured cluster "
        "membership is not retained by the runtime"
    )


def test_majority_is_derived_from_configured_cluster_size():
    """
    Majority must be calculated from configured membership.
    """

    source = _source().lower()

    assert "majority" in source, (
        "Axis 8 Contract 1A violated: runtime does not "
        "derive an explicit majority threshold"
    )

    assert "configured_cluster_size" in source, (
        "Axis 8 Contract 1A violated: majority has no "
        "stable membership authority"
    )


def test_quorum_must_not_use_dynamic_peer_count_as_cluster_size():
    """
    Dynamic Rendezvous visibility must not define total
    configured cluster membership.
    """

    source = _source().replace(" ", "")

    forbidden = (
        "configured_cluster_size=len(raw_peers)",
        "configured_cluster_size=len(self.peers)",
    )

    for expression in forbidden:
        assert expression not in source, (
            "Axis 8 Contract 1A violated: dynamic peer "
            "visibility was used as stable membership"
        )
