import time
import threading
import urllib.error

from concurrent.futures import ThreadPoolExecutor, as_completed

from torture.client import DatabaseClient
from torture.generator import WorkloadGenerator


class ConcurrencyEngine:

    def __init__(
        self,
        base_url,
        history,
        workers=4,
        operations_per_worker=100,
        seed=42
    ):
        self.base_url = base_url
        self.history = history
        self.workers = workers
        self.operations_per_worker = operations_per_worker
        self.seed = seed

        self.lock = threading.Lock()
        self.results = []
        self.completed = 0

    def _execute_operation(self, client, operation):

        start_time = time.perf_counter()

        try:
            operation_type = operation["type"]
            key = operation["key"]

            if operation_type == "PUT":
                client.put(key, operation["value"])
                outcome = "ACKNOWLEDGED"

            elif operation_type == "GET":
                value = client.get(key)
                outcome = (
                    "NOT_FOUND" if value is None
                    else "ACKNOWLEDGED"
                )

            elif operation_type == "DELETE":
                client.delete(key)
                outcome = "ACKNOWLEDGED"

            else:
                raise ValueError(
                    f"Unknown operation: {operation_type}"
                )

            error = None

        except urllib.error.HTTPError as exception:
            outcome = "REJECTED"
            error = str(exception)

        except (urllib.error.URLError, TimeoutError, OSError) as exception:
            outcome = "UNKNOWN"
            error = str(exception)

        except Exception as exception:
            outcome = "FAILED"
            error = str(exception)

        end_time = time.perf_counter()

        self.history.record(
            operation,
            outcome,
            error=error
        )

        result = {
            "operation": operation,
            "outcome": outcome,
            "error": error,
            "latency_ms": (end_time - start_time) * 1000
        }

        with self.lock:
            self.results.append(result)
            self.completed += 1

        return result

    def _worker(self, worker_id):

        client = DatabaseClient(self.base_url)

        generator = WorkloadGenerator(
            seed=self.seed + worker_id,
            keyspace=100
        )

        for _ in range(self.operations_per_worker):
            operation = generator.generate_operation()
            self._execute_operation(client, operation)

        return worker_id

    def run(self):

        print(
            f"Starting {self.workers} workers, "
            f"{self.operations_per_worker} operations each..."
        )

        start_time = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=self.workers
        ) as executor:

            futures = [
                executor.submit(self._worker, worker_id)
                for worker_id in range(self.workers)
            ]

            for future in as_completed(futures):
                future.result()

        elapsed = time.perf_counter() - start_time

        return {
            "workers": self.workers,
            "total_operations": self.completed,
            "elapsed_seconds": elapsed,
            "operations_per_second": (
                self.completed / elapsed if elapsed else 0
            ),
            "results": self.results
        }