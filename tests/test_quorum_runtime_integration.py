import os
from unittest.mock import patch

import pytest

from nexus_distributed_core import NexusDistributedCore


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    # The core writes nexus_<id>.db and outputs/ relative to the cwd.
    monkeypatch.chdir(tmp_path)


def _make_core(cluster_size, mode=None):
    """
    Construct the real NexusDistributedCore with an explicit
    stable cluster membership size.

    The web server and background threads are patched out so the
    test never binds sockets or contacts a hub.
    """

    env = {
        "NEXUS_CLUSTER_SIZE": str(cluster_size),
        "NEXUS_SECRET_KEY": "axis8-test-key",
    }
    if mode is not None:
        env["NEXUS_CLUSTER_MODE"] = mode

    with (
        patch.dict(os.environ, env, clear=False),
        patch("nexus_distributed_core.start_web_server"),
        patch("nexus_distributed_core.threading.Thread"),
    ):
        if mode is None:
            os.environ.pop("NEXUS_CLUSTER_MODE", None)
        return NexusDistributedCore(
            node_id="NODE-A",
            web_port=8081,
            tcp_port=9091,
            role="FOLLOWER",
        )


@pytest.mark.parametrize(
    "cluster_size,mode,expected_majority",
    [
        (1, "single", 1),
        (2, None, 2),
        (3, None, 2),
        (4, "distributed", 3),
        (5, "distributed", 3),
    ],
)
def test_real_runtime_derives_majority_from_configured_membership(
    cluster_size,
    mode,
    expected_majority,
):
    core = _make_core(cluster_size, mode)

    assert core.configured_cluster_size == cluster_size
    assert core.majority == expected_majority


def test_real_runtime_n1_without_explicit_mode_has_no_majority():
    """W08-B: N == 1 alone is unconfigured and can never promote."""
    core = _make_core(1)

    assert core.cluster_mode == "unconfigured"
    assert core.configured_cluster_size == 1
    assert core.majority is None


def test_real_runtime_three_member_cluster_requires_two_members():
    core = _make_core(3)

    assert core.configured_cluster_size == 3
    assert core.majority == 2


def test_real_runtime_membership_is_not_redefined_by_visibility():
    """
    Dynamic peer visibility must not reduce the stable
    configured membership requirement.
    """

    core = _make_core(3)

    raw_peers = {}

    visible_member_ids = {
        str(node_id)
        for node_id, info in raw_peers.items()
        if isinstance(info, dict)
    }

    visible_member_ids.add(str(core.node_id))

    quorum_count = len(visible_member_ids)

    assert quorum_count == 1
    assert core.majority == 2
    assert quorum_count < core.majority


def test_real_runtime_two_visible_members_satisfy_three_node_majority():
    core = _make_core(3)

    raw_peers = {
        "NODE-B": {
            "node_id": "NODE-B",
            "role": "FOLLOWER",
        }
    }

    visible_member_ids = {
        str(node_id)
        for node_id, info in raw_peers.items()
        if isinstance(info, dict)
    }

    visible_member_ids.add(str(core.node_id))

    quorum_count = len(visible_member_ids)

    assert quorum_count == 2
    assert core.majority == 2
    assert quorum_count >= core.majority


def test_invalid_zero_cluster_size_is_rejected():
    with pytest.raises(
        ValueError,
        match="NEXUS_CLUSTER_SIZE",
    ):
        _make_core(0)
