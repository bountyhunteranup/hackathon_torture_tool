import threading
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.environment import TestEnvironment


def main():
    workers = 8
    writes_per_worker = 50
    shared_key = "shared-account"

    # Inject the concurrent client into our existing environment.
    with TestEnvironment(client_class=ConcurrentDatabaseClient) as env:

        barrier = threading.Barrier(workers)
        acknowledged_values = set()
        values_lock = threading.Lock()

        def worker(worker_id):
            barrier.wait()

            for sequence in range(writes_per_worker):
                value = f"worker-{worker_id}-write-{sequence:03d}"

                started_at = datetime.now(timezone.utc).isoformat()
                start = time.perf_counter()

                try:
                    env.database.put(shared_key, value)

                    duration_ms = (
                        time.perf_counter() - start
                    ) * 1000

                    completed_at = datetime.now(timezone.utc).isoformat()

                    with values_lock:
                        acknowledged_values.add(value)

                    env.history.record(
                        {
                            "type": "PUT",
                            "key": shared_key,
                            "value": value,
                        },
                        outcome="ACKNOWLEDGED",
                        response=204,
                        verification="ACKNOWLEDGED",
                        duration_ms=duration_ms,
                        started_at=started_at,
                        completed_at=completed_at,
                    )

                except Exception as error:
                    duration_ms = (
                        time.perf_counter() - start
                    ) * 1000

                    env.history.record(
                        {
                            "type": "PUT",
                            "key": shared_key,
                            "value": value,
                        },
                        outcome="FAILED",
                        verification="NOT_RUN",
                        duration_ms=duration_ms,
                        error=str(error),
                        started_at=started_at,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    raise

        print("\n--- SAME-KEY CONTENTION TEST ---")
        print("Workers:", workers)
        print("Writes per worker:", writes_per_worker)
        print("Shared key:", shared_key)

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(worker, worker_id)
                for worker_id in range(workers)
            ]

            for future in futures:
                future.result()

        elapsed = time.perf_counter() - start

        # All workers have finished. No writes are still in flight.
        final_value = env.database.get(shared_key)

        total_writes = workers * writes_per_worker

        print("\n--- RESULTS ---")
        print("Total attempted writes:", total_writes)
        print("Acknowledged writes:", len(acknowledged_values))
        print("Elapsed seconds:", round(elapsed, 4))
        print(
            "Throughput:",
            round(total_writes / elapsed, 2),
            "writes/second",
        )
        print("Final database value:", final_value)

        # Every acknowledged PUT must have produced a complete valid value.
        assert len(acknowledged_values) == total_writes
        assert final_value in acknowledged_values

        print("\nSAME-KEY CONTENTION TEST PASSED!")


if __name__ == "__main__":
    main()
