"""Nexus Runtime Platform."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nexus-runtime-platform")
except PackageNotFoundError:
    __version__ = "2300.0.0-dev"
