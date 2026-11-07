
import random
import threading
import time

from concurrent.futures import ThreadPoolExecutor

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.environment import TestEnvironment
from torture.linearizability import is_linearizable
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=42)
args, _ = parser.parse_known_args()

SEED = args.seed

WORKERS = 4
OPERATIONS_PER_WORKER = 4

KEYS = ["account-A", "account-B", "account-C"]

print("Seed:", SEED)


def main():
    history = []
    history_lock = threading.Lock()
    errors = []

    barrier = threading.Barrier(WORKERS)

    with TestEnvironment(
        client_class=ConcurrentDatabaseClient
    ) as env:

        def worker(worker_id):
            rng = random.Random(SEED + worker_id)

            barrier.wait()

            for sequence in range(OPERATIONS_PER_WORKER):

                operation_type = rng.choice(
                    ["PUT", "GET", "DELETE"]
                )

                key = rng.choice(KEYS)

                operation = {
                    "type": operation_type,
                    "key": key,
                }

                if operation_type == "PUT":
                    operation["value"] = (
                        f"worker-{worker_id}-value-{sequence}"
                    )

                start = time.perf_counter_ns()

                try:
                    if operation_type == "PUT":
                        env.database.put(
                            key,
                            operation["value"]
                        )

                    elif operation_type == "GET":
                        operation["response"] = (
                            env.database.get(key)
                        )

                    elif operation_type == "DELETE":
                        env.database.delete(key)

                    end = time.perf_counter_ns()

                    operation["start"] = start
                    operation["end"] = end

                    with history_lock:
                        history.append(operation)

                except Exception as error:
                    with history_lock:
                        errors.append({
                            "worker": worker_id,
                            "operation": operation,
                            "error": repr(error),
                        })

                    raise

        print("\n--- MULTI-KEY LINEARIZABILITY TEST ---")

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = [
                executor.submit(worker, worker_id)
                for worker_id in range(WORKERS)
            ]

            for future in futures:
                future.result()

        print("Workers:", WORKERS)
        print("Operations recorded:", len(history))
        print("Errors:", len(errors))

        if errors:
            raise RuntimeError(
                "Operations failed or had uncertain outcomes. "
                "Do not claim linearizability from this incomplete history."
            )

        actual_final_state = env.database.dump()

        result = is_linearizable(
            history,
            initial_state={},
            final_state=actual_final_state,
        )

        print("Linearizable:", result)

        if not result:
            raise AssertionError(
                "No legal sequential execution exists!"
            )

        print("\nMULTI-KEY LINEARIZABILITY TEST PASSED!")

        print("\nFinal database state:")
        print(env.database.dump())


if __name__ == "__main__":
    main()
