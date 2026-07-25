"""Nexus Runtime Platform."""

from importlib.metadata import PackageNotFoundError, version

from .client import NexusClient
from .runtime_client import RuntimeClient
from .runtime import Runtime
from .runtime import RuntimeConfig

try:
    __version__ = version("nexus-runtime-platform")
except PackageNotFoundError:
    __version__ = "2400.0.0-dev"

__all__ = [
    "NexusClient",
    "RuntimeClient",
    "Runtime",
    "RuntimeConfig",
    "__version__",
]
