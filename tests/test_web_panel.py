import io
import json

import web_panel
from persistence import NexusPersistence
from web_panel import MetricsHTTPHandler


class FakeRuntime:
    def __init__(self, tmp_path):
        self.node_id = "NO-WEB-01"
        self.role = "FOLLOWER"
        self.web_port = 8085
        self.tcp_port = 9095
        self.term = 3
        self.persistence = NexusPersistence(
            filepath=str(tmp_path / "runtime.db")
        )
        self.peers = {
            "NO-WEB-01": {
                "node_id": "NO-WEB-01",
                "role": "FOLLOWER",
            },
            "NO-WEB-02": {
                "node_id": "NO-WEB-02",
                "role": "MASTER",
            },
        }


class FakeRequest:
    def __init__(self, path):
        self.path = path
        self.wfile = io.BytesIO()
        self.status = None
        self.headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers[name] = value

    def end_headers(self):
        pass


def make_handler(path):
    request = FakeRequest(path)
    handler = object.__new__(MetricsHTTPHandler)
    handler.path = request.path
    handler.wfile = request.wfile
    handler.send_response = request.send_response
    handler.send_header = request.send_header
    handler.end_headers = request.end_headers
    return handler, request


def read_body(request):
    return json.loads(request.wfile.getvalue().decode("utf-8"))


def test_status_endpoint_reports_runtime_state(tmp_path):
    web_panel._runtime_instance = FakeRuntime(tmp_path)
    handler, request = make_handler("/status")

    handler.do_GET()

    body = read_body(request)

    assert request.status == 200
    assert body["node_id"] == "NO-WEB-01"
    assert body["role"] == "FOLLOWER"
    assert body["web_port"] == 8085
    assert body["tcp_port"] == 9095
    assert body["height"] == 0
    assert body["term"] == 3


def test_metrics_endpoint_reports_operational_metrics(tmp_path):
    web_panel._runtime_instance = FakeRuntime(tmp_path)
    handler, request = make_handler("/metrics")

    handler.do_GET()

    body = read_body(request)

    assert request.status == 200
    assert body["status"] == "OPERATIONAL"
    assert body["engine_version"] == "Nexus Runtime v1.1 RC1"
    assert body["node_id"] == "NO-WEB-01"
    assert body["role"] == "FOLLOWER"


def test_cluster_endpoint_reports_leader_and_followers(tmp_path):
    web_panel._runtime_instance = FakeRuntime(tmp_path)
    handler, request = make_handler("/cluster")

    handler.do_GET()

    body = read_body(request)

    assert request.status == 200
    assert body["leader"] == "NO-WEB-02"
    assert body["followers"] == ["NO-WEB-01"]
    assert body["nodes"] == 2
    assert set(body["peers"]) == {"NO-WEB-01", "NO-WEB-02"}
