from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping


class ProtocolError(ValueError):
    """Mensagem de protocolo inválida, expirada ou repetida."""


@dataclass
class ReplayCache:
    _messages: dict[str, float] = field(default_factory=dict)
    _nonces: dict[tuple[str, str], float] = field(default_factory=dict)

    def purge(self, now: float, ttl: float) -> None:
        expired_messages = [
            message_id
            for message_id, timestamp in self._messages.items()
            if now - timestamp > ttl
        ]
        for message_id in expired_messages:
            del self._messages[message_id]

        expired_nonces = [
            nonce_key
            for nonce_key, timestamp in self._nonces.items()
            if now - timestamp > ttl
        ]
        for nonce_key in expired_nonces:
            del self._nonces[nonce_key]

    def contains_message(self, message_id: str, now: float, ttl: float) -> bool:
        self.purge(now, ttl)
        return message_id in self._messages

    def contains_nonce(
        self,
        sender: str,
        nonce: str,
        now: float,
        ttl: float,
    ) -> bool:
        self.purge(now, ttl)
        return (sender, nonce) in self._nonces

    def add(
        self,
        message_id: str,
        sender: str,
        nonce: str,
        timestamp: float,
    ) -> None:
        self._messages[message_id] = timestamp
        self._nonces[(sender, nonce)] = timestamp


class NexusProtocol:
    VERSION = 1
    REQUIRED_FIELDS = {
        "version",
        "message_id",
        "timestamp",
        "nonce",
        "sender",
        "type",
        "payload",
        "signature",
    }

    def __init__(self, secret_key: str):
        secret = secret_key.strip()
        if not secret:
            raise ValueError("secret key must not be empty")
        self._secret_key = secret.encode("utf-8")

    @staticmethod
    def canonical_serialize(data: Mapping[str, Any]) -> str:
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _sign_fields(self, fields: Mapping[str, Any]) -> str:
        serialized = self.canonical_serialize(fields)
        return hmac.new(
            self._secret_key,
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def create_envelope(
        self,
        *,
        sender: str,
        message_type: str,
        payload: Mapping[str, Any],
        timestamp: float | None = None,
        nonce: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        unsigned = {
            "version": self.VERSION,
            "message_id": message_id or str(uuid.uuid4()),
            "timestamp": time.time() if timestamp is None else float(timestamp),
            "nonce": nonce or uuid.uuid4().hex,
            "sender": sender,
            "type": message_type,
            "payload": dict(payload),
        }

        return {
            **unsigned,
            "signature": self._sign_fields(unsigned),
        }

    def verify_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        now: float | None = None,
        ttl: float,
        replay_cache: ReplayCache,
    ) -> bool:
        missing = self.REQUIRED_FIELDS.difference(envelope)
        if missing:
            raise ProtocolError(
                f"missing envelope fields: {sorted(missing)}"
            )

        if envelope["version"] != self.VERSION:
            raise ProtocolError("unsupported protocol version")

        if ttl <= 0:
            raise ProtocolError("ttl must be greater than zero")

        current_time = time.time() if now is None else float(now)

        try:
            timestamp = float(envelope["timestamp"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("invalid timestamp") from exc

        if current_time - timestamp > ttl:
            raise ProtocolError("expired envelope")

        if timestamp - current_time > ttl:
            raise ProtocolError("envelope timestamp is too far in the future")

        message_id = str(envelope["message_id"])
        sender = str(envelope["sender"])
        nonce = str(envelope["nonce"])

        if replay_cache.contains_message(message_id, current_time, ttl):
            raise ProtocolError("replay detected")

        if replay_cache.contains_nonce(sender, nonce, current_time, ttl):
            raise ProtocolError("nonce replay detected")

        signature = str(envelope["signature"])
        unsigned = {
            key: value
            for key, value in envelope.items()
            if key != "signature"
        }
        expected = self._sign_fields(unsigned)

        if not hmac.compare_digest(expected, signature):
            raise ProtocolError("invalid signature")

        replay_cache.add(
            message_id,
            sender,
            nonce,
            timestamp,
        )
        return True
