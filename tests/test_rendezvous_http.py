import io
import json
from http.client import responses
from unittest.mock import patch

from nexus_protocol import NexusProtocol, ReplayCache
from nexus_rendezvous import NexusRendezvousHandler


class FakeRequest:
    def __init__(self, body: bytes, path: str = "/register"):
        self.path = path
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.client_address = ("192.168.1.20", 50000)
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


def make_handler(body: bytes):
    request = FakeRequest(body)
    handler = object.__new__(NexusRendezvousHandler)
    handler.path = request.path
    handler.headers = request.headers
    handler.rfile = request.rfile
    handler.wfile = request.wfile
    handler.client_address = request.client_address
    handler.send_response = request.send_response
    handler.send_header = request.send_header
    handler.end_headers = request.end_headers
    return handler, request


def make_registration():
    protocol = NexusProtocol("test-secret")
    return protocol.create_envelope(
        sender="NO-ARM-01",
        message_type="REGISTER",
        payload={
            "node_id": "NO-ARM-01",
            "role": "FOLLOWER",
            "web_port": 8082,
            "tcp_port": 9092,
            "protocol_version": 1,
        },
        timestamp=1000.0,
        nonce="nonce-http-001",
        message_id="message-http-001",
    )


def test_http_register_accepts_valid_envelope():
    envelope = make_registration()
    handler, request = make_handler(json.dumps(envelope).encode())

    with patch("nexus_rendezvous.PROTOCOL", NexusProtocol("test-secret")), \
         patch("nexus_rendezvous.REPLAY_CACHE", ReplayCache()), \
         patch("nexus_rendezvous.time.time", return_value=1001.0):
        handler.do_POST()

    assert request.status == 200
    body = json.loads(request.wfile.getvalue().decode())
    assert body["status"] == "registered"


def test_http_register_rejects_invalid_signature():
    envelope = make_registration()
    envelope["payload"]["role"] = "MASTER"
    handler, request = make_handler(json.dumps(envelope).encode())

    with patch("nexus_rendezvous.PROTOCOL", NexusProtocol("test-secret")), \
         patch("nexus_rendezvous.REPLAY_CACHE", ReplayCache()), \
         patch("nexus_rendezvous.time.time", return_value=1001.0):
        handler.do_POST()

    assert request.status == 401


def test_http_register_rejects_invalid_json():
    handler, request = make_handler(b"{invalid-json")

    with patch("nexus_rendezvous.PROTOCOL", NexusProtocol("test-secret")), \
         patch("nexus_rendezvous.REPLAY_CACHE", ReplayCache()):
        handler.do_POST()

    assert request.status == 400
