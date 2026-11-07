"""Run and verify concurrent operations against independent key ranges."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from torture.client import DatabaseRejected, OutcomeUnknown


class ConcurrentCampaignRunner:
    """Coordinate overlapping client calls and record invocation intervals.

    Each worker owns distinct keys, so the Oracle expectations are
    deterministic while requests from different workers overlap. Conflicting
    same-key histories are left for a later linearizability checker.
    """

    def __init__(self, database, history):
        self.database = database
        self.history = history
        self.results = []
        self._results_lock = threading.Lock()

    def _execute(self, operation, action, expected):
        started_at = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()

        try:
            response = action()
        except Exception as error:
            if isinstance(error, DatabaseRejected):
                outcome = "REJECTED"
            elif isinstance(error, OutcomeUnknown):
                outcome = "UNKNOWN"
            else:
                outcome = "FAILED"

            completed_at = datetime.now(timezone.utc).isoformat()
            duration_ms = (time.perf_counter() - start) * 1000
            self.history.record(
                operation,
                outcome=outcome,
                verification="NOT_RUN",
                duration_ms=duration_ms,
                error=str(error),
                started_at=started_at,
                completed_at=completed_at,
            )
            raise

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = (time.perf_counter() - start) * 1000
        outcome = (
            "NOT_FOUND"
            if operation["type"] == "GET" and response is None
            else "ACKNOWLEDGED"
        )
        verification = "PASSED" if response == expected else "FAILED"
        error = None if verification == "PASSED" else (
            f"Expected {expected!r}, received {response!r}"
        )

        record = self.history.record(
            operation,
            outcome=outcome,
            response=response,
            verification=verification,
            duration_ms=duration_ms,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
        )
        with self._results_lock:
            self.results.append(record)

        if verification == "FAILED":
            raise AssertionError(error)
        return response

    def _run_worker(self, worker_id, rounds):
        for round_id in range(rounds):
            key = f"concurrent-{worker_id}-{round_id}"
            value = f"value-{worker_id}-{round_id}"

            self._execute(
                {"type": "PUT", "key": key, "value": value},
                lambda key=key, value=value: self.database.put(key, value),
                204,
            )
            self._execute(
                {"type": "GET", "key": key},
                lambda key=key: self.database.get(key),
                value,
            )
            self._execute(
                {"type": "DELETE", "key": key},
                lambda key=key: self.database.delete(key),
                204,
            )
            self._execute(
                {"type": "GET", "key": key},
                lambda key=key: self.database.get(key),
                None,
            )

    def run(self, workers=8, rounds_per_worker=10):
        for name, value, minimum in (
            ("workers", workers, 1),
            ("rounds_per_worker", rounds_per_worker, 0),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < minimum
            ):
                raise ValueError(f"{name} must be an integer >= {minimum}")

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self._run_worker, worker_id, rounds_per_worker)
                for worker_id in range(workers)
            ]
            for future in futures:
                future.result()

        elapsed_seconds = time.perf_counter() - start
        expected_operations = workers * rounds_per_worker * 4
        actual_state = self.database.dump()
        if actual_state:
            raise AssertionError(
                f"Expected an empty database after workers; found {len(actual_state)} keys"
            )

        return {
            "workers": workers,
            "rounds_per_worker": rounds_per_worker,
            "total_operations": expected_operations,
            "elapsed_seconds": elapsed_seconds,
            "operations_per_second": (
                expected_operations / elapsed_seconds if elapsed_seconds else 0
            ),
            "results": [
                {
                    "outcome": record["outcome"],
                    "latency_ms": record["duration_ms"],
                }
                for record in self.results
            ],
            "final_state_verified": True,
        }
