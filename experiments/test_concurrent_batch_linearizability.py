import threading
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter_ns

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.environment import TestEnvironment
from torture.linearizability import is_linearizable


def main():
    initial_state = {
        "A": "initial",
        "B": "initial",
    }

    history = []
    history_lock = threading.Lock()
    start_barrier = threading.Barrier(4)

    expected_generations = set()

    with TestEnvironment(client_class=ConcurrentDatabaseClient) as env:
        db = env.database

        # Establish the initial database state before concurrency begins.
        db.put("A", "initial")
        db.put("B", "initial")

        def writer(worker_id):
            start_barrier.wait()

            for iteration in range(2):
                generation = f"writer-{worker_id}-{iteration}"
                expected_generations.add(generation)

                operations = [
                    {"type": "PUT", "key": "A", "value": generation},
                    {"type": "PUT", "key": "B", "value": generation},
                ]

                started = perf_counter_ns()
                db.batch(operations)
                completed = perf_counter_ns()

                with history_lock:
                    history.append({
                        "type": "BATCH",
                        "operations": operations,
                        "start": started,
                        "end": completed,
                    })

        def reader():
            start_barrier.wait()

            for _ in range(2):
                for key in ("A", "B"):
                    started = perf_counter_ns()
                    value = db.get(key)
                    completed = perf_counter_ns()

                    with history_lock:
                        history.append({
                            "type": "GET",
                            "key": key,
                            "response": value,
                            "start": started,
                            "end": completed,
                        })

        # Two writers and two readers start together.
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(writer, 1),
                executor.submit(writer, 2),
                executor.submit(reader),
                executor.submit(reader),
            ]

            for future in futures:
                future.result()

        # Only inspect the database after all concurrent operations finish.
        final_state = db.dump()

        print(f"Recorded operations: {len(history)}")
        print(f"Final database state: {final_state}")

        if final_state.get("A") != final_state.get("B"):
            raise AssertionError(
                "Atomic batch invariant violated: A and B differ"
            )

        if final_state.get("A") not in expected_generations:
            raise AssertionError("Unexpected final generation")

        result = is_linearizable(
            history,
            initial_state=initial_state,
            final_state=final_state,
        )

        print(f"Linearizable: {result}")

        if not result:
            for operation in history:
                print(operation)

            raise AssertionError("Concurrent batch history is not linearizable")

        print("CONCURRENT BATCH EXPERIMENT PASSED")


if __name__ == "__main__":
    main()