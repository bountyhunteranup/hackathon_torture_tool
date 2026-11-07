import threading
import time

from concurrent.futures import ThreadPoolExecutor

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.environment import TestEnvironment


def is_linearizable(history, initial_value):
    """
    Check whether a single-key PUT/GET history has a legal
    sequential ordering that respects real-time precedence.
    """

    count = len(history)

    # predecessors[j] contains operations that must occur
    # before operation j because they completed before j started.
    predecessors = [0] * count

    for i, first in enumerate(history):
        for j, second in enumerate(history):
            if i != j and first["end"] <= second["start"]:
                predecessors[j] |= 1 << i

    full_mask = (1 << count) - 1
    failed_states = set()

    def search(done, current_value):
        if done == full_mask:
            return True

        state = (done, current_value)
        if state in failed_states:
            return False

        for i, operation in enumerate(history):
            bit = 1 << i

            if done & bit:
                continue

            # All real-time predecessors must already be placed.
            if predecessors[i] & ~done:
                continue

            if operation["type"] == "PUT":
                next_value = operation["value"]

            else:
                # A GET must observe the current sequential value.
                if operation["response"] != current_value:
                    continue

                next_value = current_value

            if search(done | bit, next_value):
                return True

        failed_states.add(state)
        return False

    return search(0, initial_value)


def main():
    writers = 2
    readers = 2
    rounds = 5
    key = "linearizable-register"
    initial_value = "initial"

    with TestEnvironment(client_class=ConcurrentDatabaseClient) as env:
        env.database.put(key, initial_value)

        barrier = threading.Barrier(writers + readers)
        history = []
        history_lock = threading.Lock()

        def record(operation):
            with history_lock:
                history.append(operation)

        def writer(worker_id):
            barrier.wait()

            for sequence in range(rounds):
                value = f"writer-{worker_id}-{sequence}"

                start = time.perf_counter_ns()
                env.database.put(key, value)
                end = time.perf_counter_ns()

                record({
                    "type": "PUT",
                    "value": value,
                    "start": start,
                    "end": end,
                })

        def reader(worker_id):
            barrier.wait()

            for sequence in range(rounds):
                start = time.perf_counter_ns()
                value = env.database.get(key)
                end = time.perf_counter_ns()

                record({
                    "type": "GET",
                    "worker": worker_id,
                    "sequence": sequence,
                    "response": value,
                    "start": start,
                    "end": end,
                })

        print("\n--- LINEARIZABILITY TEST ---")

        with ThreadPoolExecutor(
            max_workers=writers + readers
        ) as executor:
            futures = []

            for worker_id in range(writers):
                futures.append(executor.submit(writer, worker_id))

            for worker_id in range(readers):
                futures.append(executor.submit(reader, worker_id))

            for future in futures:
                future.result()

        print("Recorded operations:", len(history))

        result = is_linearizable(history, initial_value)

        print("Linearizable:", result)

        assert len(history) == writers * rounds + readers * rounds
        assert result, "No legal sequential execution exists!"

        print("\nLINEARIZABILITY TEST PASSED!")


if __name__ == "__main__":
    main()
