"""Runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RuntimeConfig:
    """Configuration for a Runtime instance."""

    node_id: str = "NODE-001"
    environment: str = "development"
    log_level: str = "INFO"

    metrics_enabled: bool = True
    tracing_enabled: bool = True
    cluster_enabled: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)
