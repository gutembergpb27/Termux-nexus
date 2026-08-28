"""Backend distribuído integrado ao RuntimeCluster."""

from __future__ import annotations

from threading import RLock

from collections.abc import Callable
from time import perf_counter
from typing import Any

from nexus.compute.backend import ComputeBackend
from nexus.compute.capabilities import BackendCapabilities
from nexus.compute.health import BackendHealth
from nexus.compute.metrics import BackendMetrics
from nexus.compute.result import ComputeResult
from nexus.compute.task import ComputeTask
from nexus.compute.task_ownership import StaleTaskOwnershipError
from nexus.runtime.cluster import RuntimeCluster

ClusterDispatcher = Callable[[ComputeTask, str], Any]


class ClusterBackend(ComputeBackend):
    """Adapta o RuntimeCluster à API Nexus Compute."""

    name = "cluster"

    def __init__(
        self,
        cluster: RuntimeCluster,
        dispatcher: ClusterDispatcher | None = None,
    ) -> None:
        self._cluster = cluster
        self._dispatcher = dispatcher
        self._terminal_results: dict[str, ComputeResult] = {}
        self._terminal_failures: dict[str, str] = {}
        self._terminal_lock = RLock()
        self._completed_runs = 0
        self._failed_runs = 0
        self._active_runs = 0
        self._total_duration_seconds = 0.0

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            compute_type="cluster",
            priority=20,
            estimated_latency_ms=10.0,
            estimated_cost=0.0,
            reliability=0.99,
            memory_mb=None,
            has_gpu=False,
        )

    def is_available(self) -> bool:
        return (
            self._dispatcher is not None
            and self._cluster.leader() is not None
            and bool(self._cluster.online_nodes())
        )

    def health(self) -> BackendHealth:
        if self._dispatcher is None:
            return BackendHealth(
                available=False,
                status="unavailable",
                message="cluster dispatcher is not configured",
            )

        if self._cluster.leader() is None:
            return BackendHealth(
                available=False,
                status="degraded",
                message="cluster leader is not elected",
            )

        if not self._cluster.online_nodes():
            return BackendHealth(
                available=False,
                status="unavailable",
                message="cluster has no online nodes",
            )

        return BackendHealth(
            available=True,
            status="healthy",
            message="cluster backend operational",
        )

    def metrics(self) -> BackendMetrics:
        return BackendMetrics(
            completed_runs=self._completed_runs,
            failed_runs=self._failed_runs,
            active_runs=self._active_runs,
            queued_tasks=0,
            total_duration_seconds=self._total_duration_seconds,
        )

    def _terminal_result(
        self,
        task_id: str,
    ) -> ComputeResult | None:
        key = str(task_id).strip()

        with self._terminal_lock:
            return self._terminal_results.get(key)

    def _publish_terminal_result(
        self,
        result: ComputeResult,
    ) -> ComputeResult:
        key = str(result.task_id).strip()

        with self._terminal_lock:
            existing = self._terminal_results.get(key)

            if existing is not None:
                return existing

            existing_failure = self._terminal_failures.get(key)

            if existing_failure is not None:
                raise RuntimeError(existing_failure)

            self._terminal_results[key] = result
            return result

    def _terminal_failure(
        self,
        task_id: str,
    ) -> str | None:
        key = str(task_id).strip()

        with self._terminal_lock:
            return self._terminal_failures.get(key)

    def publish_terminal_failure(
        self,
        task_id: str,
        error: Exception,
    ) -> str:
        """Publica uma falha somente quando ela ja e terminal."""
        key = str(task_id).strip()
        message = str(error)

        with self._terminal_lock:
            existing_result = self._terminal_results.get(key)

            if existing_result is not None:
                raise RuntimeError(
                    "task already completed authoritatively"
                )

            existing_failure = self._terminal_failures.get(key)

            if existing_failure is not None:
                return existing_failure

            self._terminal_failures[key] = message
            return message

    def run(self, task: ComputeTask) -> ComputeResult:
        health = self.health()

        if not health.available:
            raise RuntimeError(
                health.message or "cluster backend unavailable"
            )

        leader = self._cluster.leader()

        if leader is None:
            raise RuntimeError("cluster leader is not available")

        dispatcher = self._dispatcher

        if dispatcher is None:
            raise RuntimeError("cluster dispatcher is not configured")

        started = perf_counter()
        self._active_runs += 1

        try:
            output = dispatcher(task, leader)
            duration = perf_counter() - started

            candidate = ComputeResult(
                task_id=task.task_id,
                backend=self.name,
                status="completed",
                output=output,
                duration_seconds=duration,
            )

            result = self._publish_terminal_result(
                candidate
            )

            self._completed_runs += 1
            return result

        except StaleTaskOwnershipError:
            #
            # A geracao stale converge para o outcome
            # terminal autoritativo, se ele ja existir.
            #
            authoritative = self._terminal_result(
                task.task_id
            )

            if authoritative is not None:
                self._completed_runs += 1
                return authoritative

            authoritative_failure = self._terminal_failure(
                task.task_id
            )

            if authoritative_failure is not None:
                self._failed_runs += 1
                raise RuntimeError(
                    authoritative_failure
                )

            self._failed_runs += 1
            raise

        except Exception:
            self._failed_runs += 1
            raise

        finally:
            self._total_duration_seconds += (
                perf_counter() - started
            )
            self._active_runs -= 1
