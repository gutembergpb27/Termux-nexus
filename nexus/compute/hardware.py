"""Detecção conservadora de capacidades de hardware do nó."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from typing import Any


MemoryProvider = Callable[[], int | None]


def _detect_windows_memory_mb() -> int | None:
    """Detecta memória física total no Windows usando ctypes."""

    if os.name != "nt":
        return None

    try:
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)

        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
            ctypes.byref(status)
        ):
            return None

        return int(status.ullTotalPhys // (1024 * 1024))

    except Exception:
        return None


def _detect_posix_memory_mb() -> int | None:
    """Detecta memória física total em plataformas POSIX."""

    if os.name != "posix":
        return None

    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        physical_pages = os.sysconf("SC_PHYS_PAGES")

        total_bytes = int(page_size) * int(physical_pages)

        if total_bytes < 0:
            return None

        return total_bytes // (1024 * 1024)

    except (AttributeError, OSError, TypeError, ValueError):
        return None


def system_memory_mb() -> int | None:
    """Retorna memória física total em MiB quando detectável."""

    if os.name == "nt":
        return _detect_windows_memory_mb()

    if os.name == "posix":
        return _detect_posix_memory_mb()

    return None


class HardwareCapabilityDetector:
    """Detecta capacidades básicas e portáveis do nó."""

    def __init__(
        self,
        memory_provider: MemoryProvider | None = None,
    ) -> None:
        self._memory_provider = (
            memory_provider or system_memory_mb
        )

    def detect(self) -> dict[str, Any]:
        memory_mb = self._memory_provider()

        if memory_mb is not None:
            memory_mb = int(memory_mb)

            if memory_mb < 0:
                raise ValueError(
                    "memory capability must be greater "
                    "than or equal to zero"
                )

        return {
            "compute_type": "cpu",
            "memory_mb": memory_mb,
            "has_gpu": False,
        }
