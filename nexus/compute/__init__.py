"""API pública da camada Nexus Compute."""

from nexus.compute.backend import ComputeBackend
from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.health import BackendHealth
from nexus.compute.local import LocalBackend
from nexus.compute.metrics import BackendMetrics
from nexus.compute.registry import BackendRegistry
from nexus.compute.requirements import ComputeRequirements
from nexus.compute.result import ComputeResult
from nexus.compute.runtime import ComputeRuntime
from nexus.compute.scheduler import BackendScheduler
from nexus.compute.selection import BackendSelection
from nexus.compute.task import ComputeTask

__all__ = [
    "BackendCapabilities",
    "BackendHealth",
    "BackendMetrics",
    "BackendRegistry",
    "BackendScheduler",
    "BackendSelection",
    "ComputeBackend",
    "ComputeRequirements",
    "ComputeResult",
    "ComputeRuntime",
    "ComputeTask",
    "LocalBackend",
]
