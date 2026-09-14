import os
from types import SimpleNamespace

import pytest


def _majority(cluster_size: int) -> int:
    return (cluster_size // 2) + 1


def _quorum_available(
    *,
    cluster_size: int,
    self_node_id: str,
    raw_peers: dict,
) -> tuple[int, int, bool]:
    """
    Behavioral model of the Axis 8 quorum gate.

    Stable membership comes from configured cluster size.
    Dynamic peer visibility is used only to count currently
    visible members.
    """

    visible_member_ids = {
        str(node_id)
        for node_id, info in raw_peers.items()
        if isinstance(info, dict)
    }

    visible_member_ids.add(str(self_node_id))

    majority = _majority(cluster_size)
    visible = len(visible_member_ids)

    return (
        visible,
        majority,
        visible >= majority,
    )


@pytest.mark.parametrize(
    "cluster_size,expected_majority",
    [
        (1, 1),
        (2, 2),
        (3, 2),
        (4, 3),
        (5, 3),
    ],
)
def test_majority_formula(
    cluster_size,
    expected_majority,
):
    assert _majority(cluster_size) == expected_majority


def test_three_node_cluster_single_visible_member_has_no_quorum():
    visible, majority, quorum = _quorum_available(
        cluster_size=3,
        self_node_id="A",
        raw_peers={},
    )

    assert visible == 1
    assert majority == 2
    assert quorum is False


def test_three_node_cluster_two_visible_members_has_quorum():
    visible, majority, quorum = _quorum_available(
        cluster_size=3,
        self_node_id="A",
        raw_peers={
            "B": {
                "node_id": "B",
                "role": "FOLLOWER",
            }
        },
    )

    assert visible == 2
    assert majority == 2
    assert quorum is True


def test_three_node_cluster_all_members_visible_has_quorum():
    visible, majority, quorum = _quorum_available(
        cluster_size=3,
        self_node_id="A",
        raw_peers={
            "B": {
                "node_id": "B",
                "role": "FOLLOWER",
            },
            "C": {
                "node_id": "C",
                "role": "FOLLOWER",
            },
        },
    )

    assert visible == 3
    assert majority == 2
    assert quorum is True


def test_dynamic_visibility_does_not_redefine_configured_cluster_size():
    """
    Even when only one member is visible, majority remains
    derived from configured membership of 3.
    """

    visible, majority, quorum = _quorum_available(
        cluster_size=3,
        self_node_id="A",
        raw_peers={},
    )

    assert visible == 1
    assert majority == 2
    assert quorum is False
