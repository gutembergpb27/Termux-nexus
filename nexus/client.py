"""Cliente HTTP reutiliz?vel da Nexus Platform."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from nexus.exceptions import NexusClientError


class NexusClient:
    """Cliente simples para os endpoints HTTP do Nexus."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def get_json(self, url: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                payload = json.load(response)
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            OSError,
        ) as exc:
            raise NexusClientError(
                f"Falha ao consultar {url}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise NexusClientError(
                f"Resposta inv?lida recebida de {url}: esperado objeto JSON."
            )

        return payload

    def status(self, url: str) -> dict[str, Any]:
        return self.get_json(url)
