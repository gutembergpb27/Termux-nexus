"""Provider de carga dinâmica anunciada por peers do cluster."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from nexus.compute.node_load import NodeLoad


PeerSnapshotProvider = Callable[
    [],
    Mapping[str, Mapping[str, Any]],
]


class PeerLoadProvider:
    """Expõe snapshots de carga dinâmica por node_id."""

    def __init__(
        self,
        peers: PeerSnapshotProvider,
    ) -> None:
        self._peers = peers

    def __call__(
        self,
        node_id: str,
    ) -> NodeLoad | None:
        snapshot = self._peers()

        if not isinstance(snapshot, Mapping):
            return None

        peer = snapshot.get(node_id)

        if not isinstance(peer, Mapping):
            return None

        load = peer.get("load")

        if not isinstance(load, Mapping):
            return None

        return NodeLoad(
            active_tasks=int(
                load.get("active_tasks", 0)
            ),
            queued_tasks=int(
                load.get("queued_tasks", 0)
            ),
            completed_tasks=int(
                load.get("completed_tasks", 0)
            ),
            failed_tasks=int(
                load.get("failed_tasks", 0)
            ),
            average_duration_ms=float(
                load.get("average_duration_ms", 0.0)
            ),
        )
