from pathlib import Path


def test_v2700_security_trust_boundary_is_documented() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "NEXUS_V2700_SECURITY_TRUST_BOUNDARY.md"
    )

    assert path.is_file()

    content = path.read_text(encoding="utf-8").lower()

    required_contracts = (
        "shared-secret trust model",
        "untrusted boundary",
        "message authentication and integrity",
        "replay resistance",
        "distributed compute boundary",
        "rendezvous boundary",
        "transport framing",
        "confidentiality",
        "persistence integrity boundary",
        "nexus_secret_key",
        "replaycache",
        "transportnodeexecutor",
        "does not claim that the raw node-to-node compute socket is protected",
    )

    for contract in required_contracts:
        assert contract in content