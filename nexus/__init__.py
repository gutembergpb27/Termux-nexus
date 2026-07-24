"""Nexus Runtime Platform."""

from importlib.metadata import PackageNotFoundError, version

from .runtime import Runtime

try:
    __version__ = version("nexus-runtime-platform")
except PackageNotFoundError:
    __version__ = "2400.0.0-dev"

__all__ = ["Runtime", "__version__"]