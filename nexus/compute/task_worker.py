"""Worker para consumo de tarefas Nexus Compute."""

from __future__ import annotations

from threading import Event, Lock, Thread

from nexus.compute.handlers import TaskHandlerRegistry
from nexus.compute.task_completion import TaskCompletionRegistry
from nexus.compute.task_queue import TaskQueue


class TaskWorker:
    """Consome tarefas pendentes e delega execução ao registry."""

    def __init__(
        self,
        *,
        queue: TaskQueue,
        registry: TaskHandlerRegistry,
        completions: TaskCompletionRegistry | None = None,
    ) -> None:
        self._queue = queue
        self._registry = registry
        self._completions = completions
        self._stop_event = Event()
        self._lifecycle_lock = Lock()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        thread = self._thread

        return (
            thread is not None
            and thread.is_alive()
            and not self._stop_event.is_set()
        )

    def run_once(self):
        if self._queue.pending_count() == 0:
            return None

        task = self._queue.dequeue()

        try:
            result = self._registry.execute(
                task.name,
                task.payload,
            )
        except Exception as exc:
            if self._completions is not None:
                completion = self._completions.get(
                    task.task_id
                )

                if completion is not None:
                    self._completions.fail(
                        task.task_id,
                        str(exc),
                    )

            raise

        if self._completions is not None:
            completion = self._completions.get(
                task.task_id
            )

            if completion is not None:
                self._completions.complete(
                    task.task_id,
                    result,
                )

        return result

    def run_until_empty(self) -> list:
        results = []

        while self._queue.pending_count() > 0:
            results.append(
                self.run_once()
            )

        return results

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._queue.pending_count() == 0:
                self._stop_event.wait(0.01)
                continue

            try:
                self.run_once()
            except Exception:
                # A falha já é contabilizada pelo registry
                # e, quando configurado, pelo completion registry.
                continue

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self.running:
                return False

            self._stop_event.clear()

            self._thread = Thread(
                target=self._run_loop,
                daemon=True,
                name="nexus-compute-worker",
            )

            self._thread.start()

            return True

    def stop(
        self,
        *,
        timeout: float | None = None,
    ) -> bool:
        with self._lifecycle_lock:
            thread = self._thread

            if thread is None or not thread.is_alive():
                return False

            self._stop_event.set()

        thread.join(timeout=timeout)

        return not thread.is_alive()
