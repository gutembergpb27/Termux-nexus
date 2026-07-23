from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


_ALLOWED_ROLES = {"FOLLOWER", "CANDIDATE", "MASTER"}


def _required(mapping: Mapping[str, str], key: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValueError(f"missing required configuration: {key}")
    return value


def _port(mapping: Mapping[str, str], key: str) -> int:
    raw = _required(mapping, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid port for {key}") from exc

    if not 1 <= value <= 65535:
        raise ValueError(f"invalid port for {key}")

    return value


def _positive_float(mapping: Mapping[str, str], key: str) -> float:
    raw = _required(mapping, key)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid numeric value for {key}") from exc

    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")

    return value


@dataclass(frozen=True)
class NexusConfig:
    node_id: str
    role: str
    bind_host: str
    web_port: int
    tcp_port: int
    hub_url: str
    db_path: Path
    anchor_path: Path
    secret_key: str
    heartbeat_interval: float
    peer_timeout: float
    message_ttl: float

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> "NexusConfig":
        role = _required(mapping, "NEXUS_ROLE").upper()
        if role not in _ALLOWED_ROLES:
            raise ValueError(
                f"invalid role: {role}; expected one of {sorted(_ALLOWED_ROLES)}"
            )

        hub_url = _required(mapping, "NEXUS_HUB_URL")
        parsed = urlparse(hub_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("invalid hub URL")

        secret_key = str(mapping.get("NEXUS_SECRET_KEY", "")).strip()
        if not secret_key:
            raise ValueError("missing secret")

        heartbeat_interval = _positive_float(
            mapping, "NEXUS_HEARTBEAT_INTERVAL"
        )
        peer_timeout = _positive_float(mapping, "NEXUS_PEER_TIMEOUT")
        message_ttl = _positive_float(mapping, "NEXUS_MESSAGE_TTL")

        if peer_timeout <= heartbeat_interval:
            raise ValueError(
                "peer timeout must be greater than heartbeat interval"
            )

        return cls(
            node_id=_required(mapping, "NEXUS_NODE_ID"),
            role=role,
            bind_host=_required(mapping, "NEXUS_BIND_HOST"),
            web_port=_port(mapping, "NEXUS_WEB_PORT"),
            tcp_port=_port(mapping, "NEXUS_TCP_PORT"),
            hub_url=hub_url.rstrip("/"),
            db_path=Path(_required(mapping, "NEXUS_DB_PATH")),
            anchor_path=Path(_required(mapping, "NEXUS_ANCHOR_PATH")),
            secret_key=secret_key,
            heartbeat_interval=heartbeat_interval,
            peer_timeout=peer_timeout,
            message_ttl=message_ttl,
        )
