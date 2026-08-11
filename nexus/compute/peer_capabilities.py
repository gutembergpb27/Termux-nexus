"""Provider de capabilities anunciadas por peers do cluster."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any


PeerSnapshotProvider = Callable[
    [],
    Mapping[str, Mapping[str, Any]],
]


class PeerCapabilityProvider:
    """Expõe capabilities de peers por node_id."""

    def __init__(
        self,
        peers: PeerSnapshotProvider,
    ) -> None:
        self._peers = peers

    def __call__(
        self,
        node_id: str,
    ) -> dict[str, Any]:
        snapshot = self._peers()

        if not isinstance(snapshot, Mapping):
            return {
                "handlers": [],
            }

        peer = snapshot.get(node_id)

        if not isinstance(peer, Mapping):
            return {
                "handlers": [],
            }

        capabilities = peer.get("capabilities")

        if not isinstance(capabilities, Mapping):
            return {
                "handlers": [],
            }

        handlers = capabilities.get("handlers", [])

        if not isinstance(handlers, list):
            return {
                "handlers": [],
            }

        result = {
            "handlers": list(handlers),
        }

        if "compute_type" in capabilities:
            result["compute_type"] = capabilities["compute_type"]

        if "memory_mb" in capabilities:
            result["memory_mb"] = capabilities["memory_mb"]

        if "has_gpu" in capabilities:
            result["has_gpu"] = capabilities["has_gpu"]

        return deepcopy(result)
