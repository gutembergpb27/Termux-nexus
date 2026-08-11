from __future__ import annotations

from nexus.compute.hardware import HardwareCapabilityDetector


def test_detector_reports_cpu_baseline() -> None:
    detector = HardwareCapabilityDetector(
        memory_provider=lambda: 8192,
    )

    capabilities = detector.detect()

    assert capabilities["compute_type"] == "cpu"
    assert capabilities["memory_mb"] == 8192
    assert capabilities["has_gpu"] is False


def test_detector_allows_unknown_memory() -> None:
    detector = HardwareCapabilityDetector(
        memory_provider=lambda: None,
    )

    assert detector.detect() == {
        "compute_type": "cpu",
        "memory_mb": None,
        "has_gpu": False,
    }


def test_detector_rejects_negative_memory() -> None:
    detector = HardwareCapabilityDetector(
        memory_provider=lambda: -1,
    )

    try:
        detector.detect()
    except ValueError as exc:
        assert "memory" in str(exc)
    else:
        raise AssertionError(
            "negative memory capability should be rejected"
        )


def test_detector_returns_fresh_snapshot() -> None:
    detector = HardwareCapabilityDetector(
        memory_provider=lambda: 4096,
    )

    first = detector.detect()
    second = detector.detect()

    assert first == second
    assert first is not second


def test_system_memory_provider_returns_detected_memory(
    monkeypatch,
) -> None:
    import nexus.compute.hardware as hardware

    monkeypatch.setattr(
        hardware,
        "_detect_windows_memory_mb",
        lambda: 16384,
    )
    monkeypatch.setattr(
        hardware.os,
        "name",
        "nt",
    )

    assert hardware.system_memory_mb() == 16384


def test_system_memory_provider_uses_posix_detection(
    monkeypatch,
) -> None:
    import nexus.compute.hardware as hardware

    monkeypatch.setattr(
        hardware,
        "_detect_posix_memory_mb",
        lambda: 8192,
    )
    monkeypatch.setattr(
        hardware.os,
        "name",
        "posix",
    )

    assert hardware.system_memory_mb() == 8192


def test_system_memory_provider_falls_back_to_none(
    monkeypatch,
) -> None:
    import nexus.compute.hardware as hardware

    monkeypatch.setattr(
        hardware,
        "_detect_windows_memory_mb",
        lambda: None,
    )
    monkeypatch.setattr(
        hardware.os,
        "name",
        "nt",
    )

    assert hardware.system_memory_mb() is None


def test_default_detector_uses_system_memory_provider(
    monkeypatch,
) -> None:
    import nexus.compute.hardware as hardware

    monkeypatch.setattr(
        hardware,
        "system_memory_mb",
        lambda: 32768,
    )

    detector = hardware.HardwareCapabilityDetector()

    assert detector.detect() == {
        "compute_type": "cpu",
        "memory_mb": 32768,
        "has_gpu": False,
    }
