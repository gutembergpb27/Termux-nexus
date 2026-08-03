"""API pública da camada Nexus Compute."""

from nexus.compute.backend import ComputeBackend
from nexus.compute.local import LocalBackend
from nexus.compute.registry import BackendRegistry
from nexus.compute.result import ComputeResult
from nexus.compute.runtime import ComputeRuntime
from nexus.compute.task import ComputeTask

__all__ = [
    "BackendRegistry",
    "ComputeBackend",
    "ComputeResult",
    "ComputeRuntime",
    "ComputeTask",
    "LocalBackend",
]
