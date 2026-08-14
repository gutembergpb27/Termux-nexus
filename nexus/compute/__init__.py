"""API pública da camada Nexus Compute."""

from nexus.compute.backend import ComputeBackend
from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.cluster import ClusterBackend
from nexus.compute.dispatcher import ClusterDispatcher, NodeExecutor
from nexus.compute.handlers import (
    TaskHandler,
    TaskHandlerRegistry,
    TaskHandlerMetrics,
    build_default_task_registry,
)
from nexus.compute.health import BackendHealth
from nexus.compute.local import LocalBackend
from nexus.compute.metrics import BackendMetrics
from nexus.compute.node_load import NodeLoad
from nexus.compute.peer_capabilities import PeerCapabilityProvider
from nexus.compute.peer_load import PeerLoadProvider
from nexus.compute.registry import BackendRegistry
from nexus.compute.requirements import ComputeRequirements
from nexus.compute.result import ComputeResult
from nexus.compute.runtime import ComputeRuntime
from nexus.compute.scheduler import BackendScheduler
from nexus.compute.selection import BackendSelection
from nexus.compute.task import ComputeTask
from nexus.compute.task_queue import TaskQueue
from nexus.compute.transport_executor import TransportNodeExecutor

__all__ = [
    "BackendCapabilities",
    "BackendHealth",
    "BackendMetrics",
    "NodeLoad",
    "PeerCapabilityProvider",
    "PeerLoadProvider",
    "BackendRegistry",
    "BackendScheduler",
    "BackendSelection",
    "ClusterBackend",
    "ClusterDispatcher",
    "ComputeBackend",
    "ComputeRequirements",
    "ComputeResult",
    "ComputeRuntime",
    "ComputeTask",
    "TaskQueue",
    "LocalBackend",
    "TransportNodeExecutor",
    "NodeExecutor",
    "TaskHandler",
    "TaskHandlerRegistry",
    "TaskHandlerMetrics",
    "build_default_task_registry",
]
