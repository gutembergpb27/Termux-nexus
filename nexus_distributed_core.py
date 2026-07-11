from nexus_protocol import NexusProtocol
from persistence import NexusPersistence
from web_panel import start_web_server
import socket
import threading
import time
import json
import logging
import sqlite3
import os
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("nexus.core")


class NexusDistributedCore:
    def __init__(self, node_id, web_port, tcp_port, role):
        self.node_id = node_id
        self.web_port = int(web_port)
        self.tcp_port = int(tcp_port)
        self.role = role
        self.hub_url = os.getenv("NEXUS_HUB_URL", "http://127.0.0.1:8500")
        secret = os.getenv("NEXUS_SECRET_KEY", "").strip()
        self.protocol = NexusProtocol(secret)
        self.last_master_heartbeat = time.time()
        
        self.db_name = f"nexus_{self.node_id}.db"
        persistence_path = os.getenv(
            "NEXUS_DB_PATH",
            f"outputs/nexus_{self.node_id}.db",
        )
        self.persistence = NexusPersistence(filepath=persistence_path)
        self.init_db()
        
        self.web_server = start_web_server(
            self,
            self.web_port,
        )
        threading.Thread(target=self.start_tcp_server, daemon=True).start()
        threading.Thread(target=self.async_polling_loop, daemon=True).start()
        
        if self.role == "MASTER":
            threading.Thread(target=self.shell_intake_loop, daemon=True).start()
            
        logger.info("core_ready node=%s role=%s", getattr(self, "node_id", "unknown"), self.role)
        

    def build_registration_envelope(
        self,
        *,
        timestamp=None,
        nonce=None,
        message_id=None,
    ):
        return self.protocol.create_envelope(
            sender=getattr(self, "node_id", "unknown"),
            message_type="REGISTER",
            payload={
                "node_id": getattr(self, "node_id", "unknown"),
                "role": self.role,
                "web_port": self.web_port,
                "tcp_port": self.tcp_port,
                "protocol_version": 1,
            },
            timestamp=timestamp,
            nonce=nonce,
            message_id=message_id,
        )

    def build_state_summary_envelope(
        self,
        *,
        term=0,
        timestamp=None,
        nonce=None,
        message_id=None,
    ):
        return self.protocol.create_envelope(
            sender=getattr(self, "node_id", "unknown"),
            message_type="STATE_SUMMARY",
            payload=self.persistence.state_summary(term=term),
            timestamp=timestamp,
            nonce=nonce,
            message_id=message_id,
        )

    def build_heartbeat_envelope(
        self,
        *,
        timestamp=None,
        nonce=None,
        message_id=None,
    ):
        return self.protocol.create_envelope(
            sender=getattr(self, "node_id", "unknown"),
            message_type="HEARTBEAT",
            payload={"role": self.role},
            timestamp=timestamp,
            nonce=nonce,
            message_id=message_id,
        )

    def post_envelope(self, path, envelope):
        payload = json.dumps(envelope).encode("utf-8")
        request = urllib.request.Request(
            f"{self.hub_url}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status == 200
        except Exception as exc:
            logger.warning("hub_request_failed path=%s error=%s", path, exc)
            return False

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT,
                prev_hash TEXT,
                current_hash TEXT,
                votes INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def start_tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.tcp_port))
        server.listen(5)
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
            except:
                pass

    def handle_state_summary(self, conn, message):
        payload = message.get("payload", {})
        remote_height = int(payload.get("height", 0))

        response = {
            "type": "SYNC_BATCH",
            "from_height": remote_height,
            "blocks": self.persistence.blocks_from_height(
                remote_height
            ),
        }
        conn.sendall(json.dumps(response).encode("utf-8"))

    def handle_sync_batch(self, _conn, message):
        blocks = message.get("blocks", [])
        applied = self.persistence.apply_blocks(blocks)
        logger.info(
            "sync_batch_applied node=%s blocks=%s",
            getattr(self, "node_id", "unknown"),
            applied,
        )

    def dispatch_tcp_message(self, conn, message):
        handlers = {
            "STATE_SUMMARY": self.handle_state_summary,
            "SYNC_BATCH": self.handle_sync_batch,
        }

        message_type = message.get("type")
        handler = handlers.get(message_type)

        if handler is None:
            logger.warning(
                "tcp_message_unsupported node=%s type=%s",
                getattr(self, "node_id", "unknown"),
                message_type,
            )
            return

        handler(conn, message)

    def handle_client(self, conn):
        try:
            data = conn.recv(65535).decode("utf-8")
            if not data:
                return

            message = json.loads(data)
            self.dispatch_tcp_message(conn, message)

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("tcp_protocol_error node=%s error=%s", getattr(self, "node_id", "unknown"), exc)
        except Exception as exc:
            logger.exception("tcp_error node=%s error=%s", getattr(self, "node_id", "unknown"), exc)
        finally:
            conn.close()

    def sync_from_peer(self, peer):
        host = str(peer.get("ip", "")).strip()
        tcp_port = int(peer.get("tcp_port", 0))

        if not host or not 1 <= tcp_port <= 65535:
            raise ValueError("invalid peer sync address")

        request = {
            "type": "STATE_SUMMARY",
            "payload": self.persistence.state_summary(),
        }

        with socket.create_connection(
            (host, tcp_port),
            timeout=3,
        ) as conn:
            conn.sendall(json.dumps(request).encode("utf-8"))
            data = conn.recv(65535)

        if not data:
            raise ValueError("empty sync response")

        response = json.loads(data.decode("utf-8"))
        if response.get("type") != "SYNC_BATCH":
            raise ValueError("invalid sync response type")

        applied = self.persistence.apply_blocks(
            response.get("blocks", [])
        )

        logger.info(
            "peer_sync_completed node=%s peer=%s blocks=%s",
            getattr(self, "node_id", "unknown"),
            peer.get("node_id", "unknown"),
            applied,
        )
        return applied

    def async_polling_loop(self):
        logger.info("polling_started node=%s", self.node_id)
        registered = False

        while True:
            try:
                if not registered:
                    registered = self.post_envelope(
                        "/register",
                        self.build_registration_envelope(),
                    )
                    if not registered:
                        time.sleep(5)
                        continue

                time.sleep(5)
                current_time = time.time()

                if not self.post_envelope(
                    "/heartbeat",
                    self.build_heartbeat_envelope(),
                ):
                    registered = False
                    continue

                raw_peers = {}
                try:
                    with urllib.request.urlopen(
                        f"{self.hub_url}/peers",
                        timeout=2,
                    ) as response:
                        if response.status == 200:
                            raw_peers = json.loads(
                                response.read().decode("utf-8")
                            )
                except Exception as exc:
                    logger.warning("peer_fetch_failed node=%s error=%s", getattr(self, "node_id", "unknown"), exc)

                master_node = next(
                    (
                        node_id
                        for node_id, info in raw_peers.items()
                        if info.get("role") == "MASTER"
                        and node_id != self.node_id
                    ),
                    None,
                )

                if master_node:
                    self.last_master_heartbeat = current_time
                    try:
                        self.sync_from_peer(raw_peers[master_node])
                    except Exception as exc:
                        logger.warning(
                            "peer_sync_failed node=%s peer=%s error=%s",
                            getattr(self, "node_id", "unknown"),
                            master_node,
                            exc,
                        )
                else:
                    delta = current_time - self.last_master_heartbeat
                    if self.role == "FOLLOWER" and delta > 15.0:
                        logger.warning(
                            "master_missing node=%s seconds=%.1f",
                            getattr(self, "node_id", "unknown"),
                            delta,
                        )
                        logger.info(
                            "leadership_promotion_started node=%s",
                            getattr(self, "node_id", "unknown"),
                        )
                        self.role = "MASTER"
                        logger.info(
                            "leadership_promoted node=%s role=%s",
                            getattr(self, "node_id", "unknown"),
                            self.role,
                        )
                        threading.Thread(
                            target=self.shell_intake_loop,
                            daemon=True,
                        ).start()

            except Exception as exc:
                logger.exception("polling_error node=%s error=%s", getattr(self, "node_id", "unknown"), exc)

    def shell_intake_loop(self):
        while self.role == "MASTER":
            try:
                payload = input(f"[{self.node_id} Intake] Digite o payload -> ")
                if not payload: continue
                
                current_hash = self.persistence.append_transaction(
                    {
                        "event": "EDGE_AI_EVENT",
                        "data": {"payload": payload},
                    }
                )
                logger.info(
                    "event_persisted node=%s hash=%s",
                    getattr(self, "node_id", "unknown"),
                    current_hash[:12],
                )
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        print("Uso: python nexus_distributed_core.py <node_id> <web_port> <tcp_port> <role>")
    else:
        core = NexusDistributedCore(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        while True:
            time.sleep(1)
