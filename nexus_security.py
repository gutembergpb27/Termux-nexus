import hashlib
import hmac
import os
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parent / "nexus_config.env"


def _load_local_secret() -> str:
    secret = os.getenv("NEXUS_SECRET_KEY", "").strip()
    if secret:
        return secret

    if not ENV_PATH.exists():
        return ""

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key.strip() == "NEXUS_SECRET_KEY":
            return value.strip().strip('"').strip("'")

    return ""


class NexusSecurityProvider:
    @staticmethod
    def get_key() -> bytes:
        secret = _load_local_secret()
        if not secret:
            raise ValueError(
                "Erro: NEXUS_SECRET_KEY não encontrada no ambiente "
                "nem no nexus_config.env"
            )
        return secret.encode("utf-8")

    @staticmethod
    def sign_payload(payload: str) -> str:
        key = NexusSecurityProvider.get_key()
        return hmac.new(
            key,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_payload(payload: str, signature: str) -> bool:
        expected = NexusSecurityProvider.sign_payload(payload)
        return hmac.compare_digest(expected, signature)
