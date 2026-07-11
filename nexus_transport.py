import json
import struct
from typing import Any


_HEADER_SIZE = 4
_MAX_MESSAGE_SIZE = 16 * 1024 * 1024


def encode_message(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict):
        raise TypeError("message must be a dictionary")

    payload = json.dumps(
        message,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    if not payload:
        raise ValueError("empty message")

    if len(payload) > _MAX_MESSAGE_SIZE:
        raise ValueError("message too large")

    return struct.pack("!I", len(payload)) + payload


def decode_message(payload: bytes) -> dict[str, Any]:
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON message") from exc

    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")

    return message


def _recv_exact(conn: Any, size: int) -> bytes:
    chunks = []
    remaining = size

    while remaining:
        chunk = conn.recv(remaining)
        if not chunk:
            raise ConnectionError(
                "connection closed before message completed"
            )

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def send_message(conn: Any, message: dict[str, Any]) -> None:
    conn.sendall(encode_message(message))


def recv_message(conn: Any) -> dict[str, Any]:
    header = _recv_exact(conn, _HEADER_SIZE)
    payload_size = struct.unpack("!I", header)[0]

    if payload_size <= 0:
        raise ValueError("invalid message size")

    if payload_size > _MAX_MESSAGE_SIZE:
        raise ValueError("message too large")

    return decode_message(_recv_exact(conn, payload_size))
