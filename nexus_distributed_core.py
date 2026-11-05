from nexus.compute.handlers import TaskHandlerRegistry, build_default_task_registry
from nexus.compute.hardware import HardwareCapabilityDetector
from nexus.compute.node_load import NodeLoad
from nexus.compute.task import ComputeTask
from nexus.compute.task_completion import TaskCompletionRegistry
from nexus.compute.task_queue import TaskQueue
from nexus.compute.task_worker import TaskWorker
from nexus_cluster_mode import (
    MODE_DISTRIBUTED,
    MODE_SINGLE,
    MODE_UNCONFIGURED,
    resolve_cluster_mode,
)
from nexus_protocol import NexusProtocol, ReplayCache
from nexus_transport import recv_message, send_message
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
    def reconcile_master_role(self, peers):
        """Resolve concurrent MASTER roles deterministically.

        The node with the lexicographically greatest stable node_id
        retains MASTER. A lower-id local MASTER yields to FOLLOWER.

        Node identity is never mutated.
        """

        if self.role != "MASTER":
            return False

        if not isinstance(peers, dict):
            return False

        local_node_id = str(self.node_id)

        for peer_id, peer in peers.items():
            if str(peer_id) == local_node_id:
                continue

            if not isinstance(peer, dict):
                continue

            if str(peer.get("role", "")).upper() != "MASTER":
                continue

            remote_node_id = str(
                peer.get("node_id", peer_id)
            )

            if remote_node_id > local_node_id:
                self.role = "FOLLOWER"
                return True

        return False

    def __init__(self, node_id, web_port, tcp_port, role):
        self.node_id = node_id
        self.web_port = int(web_port)
        self.tcp_port = int(tcp_port)
        self.role = role

        # W08-B: explicit, fail-closed cluster mode. Invalid values raise
        # here, before any file, socket or thread is created.
        cluster = resolve_cluster_mode(os.environ)
        self.cluster_mode = cluster.mode
        self.configured_cluster_size = cluster.cluster_size
        # None blocks leadership promotion (unconfigured mode).
        self.majority = cluster.majority
        logger.info(
            "cluster_mode_resolved node=%s mode=%s cluster_size=%s "
            "majority=%s local_writes=%s peer_sync=disabled",
            node_id,
            cluster.mode,
            cluster.cluster_size,
            cluster.majority,
            "allowed" if cluster.local_writes_allowed else "blocked",
        )

        self.hub_url = os.getenv("NEXUS_HUB_URL", "http://127.0.0.1:8500")
        secret = os.getenv("NEXUS_SECRET_KEY", "").strip()
        self.protocol = NexusProtocol(secret)
        self.compute_replay_cache = ReplayCache()
        self.liveness_replay_cache = ReplayCache()
        self.liveness_lock = threading.Lock()
        self.compute_task_handlers = build_default_task_registry()
        self.compute_task_queue = TaskQueue()
        self.compute_task_completions = TaskCompletionRegistry()
        self.compute_task_worker = TaskWorker(
            queue=self.compute_task_queue,
            registry=self.compute_task_handlers,
            completions=self.compute_task_completions,
        )
        self.hardware_capability_detector = HardwareCapabilityDetector()
        self.compute_message_ttl = float(
            os.getenv("NEXUS_MESSAGE_TTL", "60.0")
        )
        if self.compute_message_ttl <= 0:
            raise ValueError(
                "NEXUS_MESSAGE_TTL must be greater than zero"
            )

        self.compute_completion_retention_seconds = float(
            os.getenv(
                "NEXUS_COMPLETION_RETENTION_SECONDS",
                "300.0",
            )
        )
        if self.compute_completion_retention_seconds <= 0:
            raise ValueError(
                "NEXUS_COMPLETION_RETENTION_SECONDS "
                "must be greater than zero"
            )
        self.last_master_heartbeat = time.time()
        self.peers = {}
        
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
        

    def runtime_health(self):
        try:
            self.persistence.validate_chain()
            summary = self.persistence.state_summary(
                term=getattr(self, "term", 0)
            )
            return {
                "healthy": True,
                "node_id": self.node_id,
                "role": self.role,
                "storage": {
                    "valid": True,
                    "height": summary["height"],
                    "tip_hash": summary["tip_hash"],
                },
            }
        except Exception as exc:
            return {
                "healthy": False,
                "node_id": getattr(self, "node_id", "unknown"),
                "role": getattr(self, "role", "UNKNOWN"),
                "storage": {
                    "valid": False,
                },
                "reason": str(exc),
            }

    def runtime_readiness(self, *, now=None, heartbeat_ttl=15.0):
        current_time = time.time() if now is None else float(now)
        role = getattr(self, "role", "UNKNOWN")
        health = self.runtime_health()

        result = {
            "ready": False,
            "node_id": getattr(self, "node_id", "unknown"),
            "role": role,
            "peers_known": len(getattr(self, "peers", {})),
        }

        if not health.get("healthy"):
            result["reason"] = "storage_unhealthy"
            return result

        if role == "MASTER":
            result["ready"] = True
            result["reason"] = "master_operational"
            return result

        if role != "FOLLOWER":
            result["reason"] = "invalid_role"
            return result

        peers = getattr(self, "peers", {})
        masters = [
            node_id
            for node_id, info in peers.items()
            if info.get("role") == "MASTER"
            and node_id != getattr(self, "node_id", None)
        ]

        if len(masters) != 1:
            result["reason"] = (
                "master_missing" if not masters else "multiple_masters"
            )
            return result

        heartbeat_age = (
            current_time
            - float(getattr(self, "last_master_heartbeat", 0.0))
        )
        result["leader"] = masters[0]
        result["master_heartbeat_age"] = heartbeat_age

        if heartbeat_age > float(heartbeat_ttl):
            result["reason"] = "master_heartbeat_stale"
            return result

        result["ready"] = True
        result["reason"] = "follower_operational"
        return result

    def hardware_capabilities(self):
        detector = getattr(
            self,
            "hardware_capability_detector",
            None,
        )

        if detector is None:
            detector = HardwareCapabilityDetector()

        return detector.detect()

    def compute_node_load(self) -> NodeLoad:
        registry = getattr(
            self,
            "compute_task_handlers",
            None,
        )

        if registry is None:
            load = NodeLoad()
        else:
            load = registry.load_snapshot()

        queue = getattr(
            self,
            "compute_task_queue",
            None,
        )

        queued_tasks = 0

        if queue is not None:
            queued_tasks = queue.pending_count()

        return NodeLoad(
            active_tasks=load.active_tasks,
            queued_tasks=queued_tasks,
            completed_tasks=load.completed_tasks,
            failed_tasks=load.failed_tasks,
            average_duration_ms=load.average_duration_ms,
        )

    def compute_capabilities(self):
        registry = getattr(
            self,
            "compute_task_handlers",
            None,
        )

        handlers = []

        if registry is not None:
            handlers = list(registry.names())

        hardware = self.hardware_capabilities()

        return {
            "handlers": handlers,
            "compute_type": hardware.get(
                "compute_type",
                "cpu",
            ),
            "memory_mb": hardware.get(
                "memory_mb",
            ),
            "has_gpu": bool(
                hardware.get(
                    "has_gpu",
                    False,
                )
            ),
        }

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
                "capabilities": self.compute_capabilities(),
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
            payload={
                "role": self.role,
                "capabilities": self.compute_capabilities(),
                "load": self.compute_node_load().to_dict(),
            },
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

    # ------------------------------------------------------------------
    # QS-C01: fail-closed distributed sync and writes.
    # ------------------------------------------------------------------

    def _distributed_sync_enabled(self):
        """Legacy peer sync is disabled in every cluster mode.

        STATE_SUMMARY / SYNC_BATCH are unauthenticated and carry no term
        or quorum. Before W08-B they were enabled whenever the cluster
        size was 1, which was also the default when NEXUS_CLUSTER_SIZE was
        missing. An explicit single-node deployment has no peer to sync
        with, so the path stays fail-closed until an authenticated
        quorum-commit protocol exists.
        """
        return False

    def _local_write_block_reason(self):
        """Return None when a local write is allowed, else a reason code.

        Only an explicit single-node deployment may write. Hub peer
        visibility can only restrict this decision, never authorize it:
        an empty or unreachable hub view does not prove the node is
        alone (single mode is an operator assertion, not a safety
        mechanism against hidden or partitioned nodes).
        """
        mode = getattr(self, "cluster_mode", None)

        if mode == MODE_SINGLE:
            size = getattr(self, "configured_cluster_size", None)
            if not (type(size) is int and size == 1):
                return "cluster_mode_invalid"

            peers = getattr(self, "peers", None)
            if peers is not None and not isinstance(peers, dict):
                return "single_mode_hub_view_invalid"

            local_id = str(getattr(self, "node_id", ""))
            if peers and any(
                str(peer_id) != local_id for peer_id in peers
            ):
                return "single_mode_peer_conflict"

            return None

        if mode == MODE_DISTRIBUTED:
            return "quorum_commit_not_implemented"

        if mode in (None, MODE_UNCONFIGURED):
            return "cluster_mode_unconfigured"

        return "cluster_mode_invalid"

    def _block_distributed_sync(self, operation):
        logger.warning(
            "distributed_sync_blocked "
            "node=%s operation=%s reason=quorum_commit_not_implemented",
            getattr(self, "node_id", "unknown"),
            operation,
        )
        raise RuntimeError(
            "distributed sync disabled until quorum commit is implemented"
        )

    # ------------------------------------------------------------------
    # MASTER liveness probe (no state transfer).
    #
    # Hub advertisement is discovery, not proof of liveness. A follower
    # refreshes MASTER liveness only after an authenticated, request-bound
    # acknowledgement in which the advertised MASTER confirms it still
    # holds the MASTER role.
    # ------------------------------------------------------------------

    MASTER_PROBE_TIMEOUT = 3.0

    def _liveness_replay_cache(self):
        cache = getattr(self, "liveness_replay_cache", None)
        if cache is None:
            cache = ReplayCache()
            self.liveness_replay_cache = cache
        return cache

    def _liveness_message_ttl(self):
        return float(getattr(self, "compute_message_ttl", 60.0))

    def _verify_liveness_envelope(self, envelope):
        """Verify HMAC, TTL and replay atomically.

        ReplayCache is not thread-safe (check-then-add), and the polling
        thread and TCP handler threads share the liveness cache.
        """
        lock = getattr(self, "liveness_lock", None)
        if lock is None:
            lock = threading.Lock()
            self.liveness_lock = lock

        with lock:
            return self.protocol.verify_envelope(
                envelope,
                now=time.time(),
                ttl=self._liveness_message_ttl(),
                replay_cache=self._liveness_replay_cache(),
            )

    def build_master_probe_envelope(self, master_id):
        return self.protocol.create_envelope(
            sender=str(getattr(self, "node_id", "unknown")),
            message_type="MASTER_PROBE",
            payload={"target": str(master_id)},
        )

    def verify_master_probe_ack(self, master_id, request, response):
        if not isinstance(response, dict):
            raise ValueError("invalid master probe response")

        self._verify_liveness_envelope(response)

        if response.get("type") != "MASTER_PROBE_ACK":
            raise ValueError("invalid master probe response type")

        if str(response.get("sender")) != str(master_id):
            raise ValueError("master probe identity mismatch")

        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("invalid master probe payload")

        if str(payload.get("request_id")) != str(request["message_id"]):
            raise ValueError("master probe response not bound to request")

        if str(payload.get("probe_sender")) != str(request["sender"]):
            raise ValueError("master probe response not bound to sender")

        if str(payload.get("role", "")).upper() != "MASTER":
            raise ValueError("advertised master no longer holds MASTER role")

        return True

    def probe_master_liveness(self, master_id, peer):
        """Prove that the advertised MASTER is alive and still MASTER.

        Raises on any failure. Never reads or writes persistent state.
        """
        if not isinstance(peer, dict):
            raise ValueError("invalid master peer record")

        host = str(peer.get("ip", "")).strip()
        try:
            tcp_port = int(peer.get("tcp_port", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid master probe address") from exc

        if not host or not 1 <= tcp_port <= 65535:
            raise ValueError("invalid master probe address")

        request = self.build_master_probe_envelope(master_id)

        with socket.create_connection(
            (host, tcp_port),
            timeout=self.MASTER_PROBE_TIMEOUT,
        ) as conn:
            send_message(conn, request)
            response = recv_message(conn)

        return self.verify_master_probe_ack(master_id, request, response)

    def handle_master_probe(self, conn, message):
        self._verify_liveness_envelope(message)

        if message.get("type") != "MASTER_PROBE":
            raise ValueError("invalid master probe type")

        payload = message.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("invalid master probe payload")

        if str(payload.get("target")) != str(self.node_id):
            raise ValueError("master probe target mismatch")

        response = self.protocol.create_envelope(
            sender=str(self.node_id),
            message_type="MASTER_PROBE_ACK",
            payload={
                "role": str(self.role),
                "request_id": str(message["message_id"]),
                "probe_sender": str(message["sender"]),
            },
        )
        send_message(conn, response)

    def handle_state_summary(self, conn, message):
        # QS-C01: serving blocks is part of distributed sync.
        if not self._distributed_sync_enabled():
            self._block_distributed_sync("state_summary")

        payload = message.get("payload", {})
        remote_height = int(payload.get("height", 0))

        response = {
            "type": "SYNC_BATCH",
            "from_height": remote_height,
            "blocks": self.persistence.blocks_from_height(
                remote_height
            ),
        }
        send_message(conn, response)

    def handle_sync_batch(self, _conn, message):
        # QS-C01 / STAGE B.3: fail-closed sync.
        if not self._distributed_sync_enabled():
            self._block_distributed_sync("sync_batch")

        blocks = message.get("blocks", [])
        applied = self.persistence.apply_blocks(blocks)
        logger.info(
            "sync_batch_applied node=%s blocks=%s",
            getattr(self, "node_id", "unknown"),
            applied,
        )

    def start_compute_worker(self) -> bool:
        worker = getattr(
            self,
            "compute_task_worker",
            None,
        )

        if worker is None:
            raise RuntimeError(
                "compute task worker is not configured"
            )

        return worker.start()

    def stop_compute_worker(
        self,
        *,
        timeout: float | None = None,
    ) -> bool:
        worker = getattr(
            self,
            "compute_task_worker",
            None,
        )

        if worker is None:
            return False

        return worker.stop(
            timeout=timeout
        )

    def compute_completion_snapshot(
        self,
    ):
        completions = getattr(
            self,
            "compute_task_completions",
            None,
        )

        if completions is None:
            raise RuntimeError(
                "compute task completions are not configured"
            )

        return completions.snapshot()

    def cleanup_compute_completions(
        self,
        *,
        max_age: float,
    ) -> int:
        completions = getattr(
            self,
            "compute_task_completions",
            None,
        )

        if completions is None:
            raise RuntimeError(
                "compute task completions are not configured"
            )

        return completions.cleanup(
            max_age=max_age,
        )

    def submit_compute_task(
        self,
        task: ComputeTask,
    ):
        retention = getattr(
            self,
            "compute_completion_retention_seconds",
            None,
        )

        if retention is not None:
            self.cleanup_compute_completions(
                max_age=retention,
            )

        queue = getattr(
            self,
            "compute_task_queue",
            None,
        )

        if queue is None:
            raise RuntimeError(
                "compute task queue is not configured"
            )

        completions = getattr(
            self,
            "compute_task_completions",
            None,
        )

        if completions is None:
            raise RuntimeError(
                "compute task completions are not configured"
            )

        registry = getattr(
            self,
            "compute_task_handlers",
            None,
        )

        if registry is None:
            raise RuntimeError(
                "compute task handlers are not configured"
            )

        # Admission validation: reject an unknown handler before
        # creating a completion or placing the task in the queue.
        registry.get(task.name)

        completion = completions.create(
            task.task_id
        )

        queue.enqueue(task)

        return completion

    def wait_for_compute_task(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ):
        completions = getattr(
            self,
            "compute_task_completions",
            None,
        )

        if completions is None:
            raise RuntimeError(
                "compute task completions are not configured"
            )

        return completions.wait(
            task_id,
            timeout=timeout,
        )

    def execute_queued_compute_task(
        self,
        task: ComputeTask,
    ):
        queue = getattr(
            self,
            "compute_task_queue",
            None,
        )

        if queue is None:
            raise RuntimeError(
                "compute task queue is not configured"
            )

        worker = getattr(
            self,
            "compute_task_worker",
            None,
        )

        completions = getattr(
            self,
            "compute_task_completions",
            None,
        )

        if worker is not None and completions is not None:
            completions.create(
                task.task_id
            )

            queue.enqueue(task)

            return worker.run_once()

        registry = getattr(
            self,
            "compute_task_handlers",
            None,
        )

        if registry is None:
            raise RuntimeError(
                "compute task handlers are not configured"
            )

        queue.enqueue(task)

        queued_task = queue.dequeue()

        return registry.execute(
            queued_task.name,
            queued_task.payload,
        )

    def handle_compute_task(self, conn, message):
        self.protocol.verify_envelope(
            message,
            now=time.time(),
            ttl=self.compute_message_ttl,
            replay_cache=self.compute_replay_cache,
        )

        if message.get("type") != "COMPUTE_TASK":
            raise ValueError("invalid compute request type")

        payload = message.get("payload")

        if not isinstance(payload, dict):
            raise ValueError(
                "compute task payload envelope must be an object"
            )

        task_id = str(payload.get("task_id", "")).strip()
        name = str(payload.get("name", "")).strip()
        task_payload = payload.get("task_payload", {})

        if not task_id:
            raise ValueError("compute task id must not be empty")

        if not name:
            raise ValueError("compute task name must not be empty")

        if not isinstance(task_payload, dict):
            raise ValueError(
                "compute task payload must be an object"
            )

        task = ComputeTask(
            name=name,
            payload=task_payload,
            task_id=task_id,
        )

        self.submit_compute_task(
            task
        )

        worker = getattr(
            self,
            "compute_task_worker",
            None,
        )

        if worker is None:
            raise RuntimeError(
                "compute task worker is not configured"
            )

        if not worker.running:
            worker.start()

        node_id = getattr(
            self,
            "node_id",
            "unknown",
        )

        try:
            completion = self.wait_for_compute_task(
                task_id,
                timeout=self.compute_message_ttl,
            )
        except TimeoutError as exc:
            response_payload = {
                "task_id": task_id,
                "status": "timeout",
                "node_id": node_id,
                "error": str(
                    exc
                    or "task completion timed out"
                ),
            }
        else:
            if completion.status == "failed":
                response_payload = {
                    "task_id": task_id,
                    "status": "failed",
                    "node_id": node_id,
                    "error": (
                        completion.error
                        or "compute task failed"
                    ),
                }
            else:
                response_payload = {
                    "task_id": task_id,
                    "status": "completed",
                    "node_id": node_id,
                    "output": completion.result,
                }

        response = self.protocol.create_envelope(
            sender=getattr(self, "node_id", "unknown"),
            message_type="COMPUTE_RESULT",
            payload=response_payload,
        )

        send_message(conn, response)

        logger.info(
            "secure_compute_task_completed "
            "node=%s task_id=%s sender=%s",
            getattr(self, "node_id", "unknown"),
            task_id,
            message.get("sender"),
        )

    def dispatch_tcp_message(self, conn, message):
        handlers = {
            "STATE_SUMMARY": self.handle_state_summary,
            "SYNC_BATCH": self.handle_sync_batch,
            "COMPUTE_TASK": self.handle_compute_task,
            "MASTER_PROBE": self.handle_master_probe,
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
            message = recv_message(conn)
            self.dispatch_tcp_message(conn, message)

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("tcp_protocol_error node=%s error=%s", getattr(self, "node_id", "unknown"), exc)
        except Exception as exc:
            logger.exception("tcp_error node=%s error=%s", getattr(self, "node_id", "unknown"), exc)
        finally:
            conn.close()

    def sync_from_peer(self, peer):
        # QS-C01 / STAGE B.3: fail-closed sync.
        if not self._distributed_sync_enabled():
            self._block_distributed_sync("sync_from_peer")

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
            send_message(conn, request)
            response = recv_message(conn)
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

                self.peers = raw_peers

                role_changed = self.reconcile_master_role(raw_peers)

                if role_changed:
                    if not self.post_envelope(
                        "/heartbeat",
                        self.build_heartbeat_envelope(),
                    ):
                        registered = False
                        continue

                master_node = next(
                    (
                        node_id
                        for node_id, info in raw_peers.items()
                        if info.get("role") == "MASTER"
                        and node_id != self.node_id
                    ),
                    None,
                )

                master_reachable = False

                if master_node and self.role == "FOLLOWER":
                    try:
                        # Liveness and sync are separate concerns.
                        # Legacy sync is disabled in every mode
                        # (QS-C01 / W08-B), so MASTER liveness is
                        # always proved with an authenticated probe.
                        if self._distributed_sync_enabled():
                            self.sync_from_peer(raw_peers[master_node])
                        else:
                            self.probe_master_liveness(
                                master_node,
                                raw_peers[master_node],
                            )
                        self.last_master_heartbeat = current_time
                        master_reachable = True
                    except Exception as exc:
                        logger.warning(
                            "peer_sync_failed node=%s peer=%s error=%s",
                            getattr(self, "node_id", "unknown"),
                            master_node,
                            exc,
                        )

                if self.role == "FOLLOWER" and not master_reachable:
                    delta = current_time - self.last_master_heartbeat
                    if self.role == "FOLLOWER" and delta > 15.0:
                        logger.warning(
                            "master_missing node=%s seconds=%.1f",
                            getattr(self, "node_id", "unknown"),
                            delta,
                        )

                        eligible_candidate_ids = [
                            str(node_id)
                            for node_id, info in raw_peers.items()
                            if (
                                str(node_id) != str(self.node_id)
                                and isinstance(info, dict)
                                and str(
                                    info.get("role", "")
                                ).upper() == "FOLLOWER"
                            )
                        ]

                        eligible_candidate_ids.append(
                            str(self.node_id)
                        )

                        promotion_candidate = max(
                            eligible_candidate_ids
                        )

                        if str(self.node_id) != promotion_candidate:
                            logger.info(
                                "leadership_promotion_deferred "
                                "node=%s candidate=%s",
                                getattr(
                                    self,
                                    "node_id",
                                    "unknown",
                                ),
                                promotion_candidate,
                            )
                            continue

                        visible_member_ids = {
                            str(node_id)
                            for node_id, info in raw_peers.items()
                            if isinstance(info, dict)
                        }
                        visible_member_ids.add(str(self.node_id))

                        # W08-B: an unconfigured or invalid cluster
                        # mode has no majority and never promotes.
                        # A single-node deployment that sees other
                        # members is misconfigured and must not
                        # promote either.
                        # Pre-existing behavior kept below: distributed
                        # promotion still counts hub-visible members.
                        # That count is not quorum proof; the MASTER
                        # role it yields is a label with no write or
                        # sync authority (both stay blocked).
                        majority = getattr(self, "majority", None)
                        single_conflict = (
                            getattr(self, "cluster_mode", None)
                            == MODE_SINGLE
                            and len(visible_member_ids) > 1
                        )
                        if (
                            type(majority) is not int
                            or majority < 1
                            or single_conflict
                        ):
                            logger.warning(
                                "leadership_promotion_blocked_cluster_mode "
                                "node=%s mode=%s majority=%s visible=%s",
                                getattr(self, "node_id", "unknown"),
                                getattr(self, "cluster_mode", None),
                                majority,
                                len(visible_member_ids),
                            )
                            continue

                        quorum_count = len(visible_member_ids)
                        quorum_available = (
                            quorum_count >= self.majority
                        )

                        if not quorum_available:
                            logger.warning(
                                "leadership_promotion_blocked_no_quorum "
                                "node=%s visible=%s majority=%s "
                                "configured_cluster_size=%s",
                                getattr(
                                    self,
                                    "node_id",
                                    "unknown",
                                ),
                                quorum_count,
                                self.majority,
                                self.configured_cluster_size,
                            )
                            continue

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
                if not payload:
                    continue

                # QS-C01 / STAGE A and W08-B:
                # A multi-node deployment must not report local
                # persistence as a distributed commit, and a missing
                # or invalid cluster mode must not be mistaken for a
                # single-node deployment. Only an explicit
                # NEXUS_CLUSTER_MODE=single may write locally.
                block_reason = self._local_write_block_reason()
                if block_reason is not None:
                    logger.warning(
                        "distributed_write_blocked node=%s reason=%s",
                        self.node_id,
                        block_reason,
                    )
                    print(
                        f"[{self.node_id} Intake] Escrita BLOQUEADA "
                        f"({block_reason}): somente "
                        "NEXUS_CLUSTER_MODE=single explícito permite "
                        "escrita local; commit distribuído por quorum "
                        "ainda não implementado (NEXUS_CLUSTER_MODE="
                        f"{getattr(self, 'cluster_mode', None)}, "
                        "NEXUS_CLUSTER_SIZE="
                        f"{getattr(self, 'configured_cluster_size', None)}"
                        "). Payload não persistido.",
                        flush=True,
                    )
                    continue

                # Revalidate after blocking input().
                if self.role != "MASTER":
                    logger.warning(
                        "write_blocked_role_changed node=%s role=%s",
                        self.node_id,
                        self.role,
                    )
                    print(
                        f"[{self.node_id} Intake] Escrita BLOQUEADA: "
                        f"o nó não é mais MASTER (role={self.role}). "
                        "Payload não persistido.",
                        flush=True,
                    )
                    continue

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
