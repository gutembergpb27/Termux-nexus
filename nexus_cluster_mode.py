"""Explicit, fail-closed cluster mode resolution (W08-B / PR-B).

Before this module the runtime read ``NEXUS_CLUSTER_SIZE`` with a default
of ``"1"`` and treated N == 1 as a trusted single-node deployment. A
multi-node deployment that simply omitted the variable therefore ran with
majority 1, local writes enabled and the legacy unauthenticated peer sync
enabled.

Rules enforced here:

* ``NEXUS_CLUSTER_MODE=single``: an explicit one-node deployment. Local
  writes may be allowed by the runtime. ``NEXUS_CLUSTER_SIZE`` must be
  absent or ``1``.
* ``NEXUS_CLUSTER_MODE=distributed``: requires ``NEXUS_CLUSTER_SIZE >= 2``.
  Writes and peer sync stay blocked (QS-C01): no quorum-commit protocol
  exists yet.
* Mode absent:
    - ``NEXUS_CLUSTER_SIZE`` absent or ``1``: UNCONFIGURED. Writes, peer
      sync and leadership promotion are blocked. ``N == 1`` alone no longer
      implies a trusted single-node deployment.
    - ``NEXUS_CLUSTER_SIZE >= 2``: treated as distributed (keeps existing
      multi-node launch scripts working; everything stays blocked).
* Any other value raises ``ValueError`` so the node refuses to start.

``single`` is an operator assertion, not a safety mechanism. The runtime
cannot prove that no other node exists: the hub peer list is
unauthenticated and may be empty because the hub is down, partitioned or
simply not shared. The runtime only uses visible peers to *refuse* writes
and promotion (``single_mode_peer_conflict``); an empty list never proves
the node is alone. Running ``single`` on more than one node reintroduces
independent, divergent writers.

Nothing here implements or certifies distributed consensus. Hub peer
visibility is never an input to this resolution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

MODE_SINGLE = "single"
MODE_DISTRIBUTED = "distributed"
MODE_UNCONFIGURED = "unconfigured"

MODE_ENV = "NEXUS_CLUSTER_MODE"
SIZE_ENV = "NEXUS_CLUSTER_SIZE"

_DECIMAL = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class ClusterMode:
    mode: str
    cluster_size: int | None
    majority: int | None

    @property
    def local_writes_allowed(self) -> bool:
        """Only an explicit single-node deployment may write locally."""
        return self.mode == MODE_SINGLE

    @property
    def promotion_allowed(self) -> bool:
        return self.majority is not None


def _read(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_size(raw: str) -> int:
    if not _DECIMAL.fullmatch(raw):
        raise ValueError(
            f"{SIZE_ENV} must be a positive integer, got {raw!r}"
        )
    size = int(raw)
    if size < 1:
        raise ValueError(f"{SIZE_ENV} must be greater than zero")
    return size


def _majority(size: int) -> int:
    return size // 2 + 1


def resolve_cluster_mode(env: Mapping[str, str]) -> ClusterMode:
    raw_mode = _read(env, MODE_ENV)
    raw_size = _read(env, SIZE_ENV)
    size = None if raw_size is None else _parse_size(raw_size)

    if raw_mode is None:
        if size is None or size == 1:
            return ClusterMode(MODE_UNCONFIGURED, size, None)
        return ClusterMode(MODE_DISTRIBUTED, size, _majority(size))

    mode = raw_mode.lower()

    if mode == MODE_SINGLE:
        if size not in (None, 1):
            raise ValueError(
                f"{MODE_ENV}=single conflicts with {SIZE_ENV}={size}"
            )
        return ClusterMode(MODE_SINGLE, 1, 1)

    if mode == MODE_DISTRIBUTED:
        if size is None or size < 2:
            raise ValueError(
                f"{MODE_ENV}=distributed requires {SIZE_ENV} >= 2"
            )
        return ClusterMode(MODE_DISTRIBUTED, size, _majority(size))

    raise ValueError(
        f"{MODE_ENV} must be 'single' or 'distributed', got {raw_mode!r}"
    )
