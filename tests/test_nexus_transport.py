import json
import struct

import pytest

from nexus_transport import (
    decode_message,
    encode_message,
    recv_message,
    send_message,
)


class FragmentedSocket:
    def __init__(self, incoming=b"", chunk_size=3):
        self.incoming = incoming
        self.chunk_size = chunk_size
        self.sent = b""

    def recv(self, size):
        if not self.incoming:
            return b""

        size = min(size, self.chunk_size)
        chunk = self.incoming[:size]
        self.incoming = self.incoming[size:]
        return chunk

    def sendall(self, data):
        self.sent += data


def test_encode_and_decode_message():
    message = {
        "type": "STATE_SUMMARY",
        "payload": {"height": 42},
    }

    frame = encode_message(message)
    payload_size = struct.unpack("!I", frame[:4])[0]

    assert payload_size == len(frame[4:])
    assert decode_message(frame[4:]) == message


def test_send_and_receive_fragmented_message():
    message = {
        "type": "SYNC_BATCH",
        "blocks": [{"payload": "x" * 10000}],
    }

    sender = FragmentedSocket()
    send_message(sender, message)

    receiver = FragmentedSocket(sender.sent, chunk_size=7)

    assert recv_message(receiver) == message


def test_recv_message_rejects_truncated_payload():
    payload = json.dumps({"type": "TEST"}).encode("utf-8")
    frame = struct.pack("!I", len(payload) + 10) + payload
    receiver = FragmentedSocket(frame)

    with pytest.raises(ConnectionError, match="completed"):
        recv_message(receiver)


def test_decode_message_rejects_non_object_json():
    with pytest.raises(ValueError, match="JSON object"):
        decode_message(b'["not", "an", "object"]')
