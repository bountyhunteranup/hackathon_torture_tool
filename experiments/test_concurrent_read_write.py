import threading
import time

from concurrent.futures import ThreadPoolExecutor

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.environment import TestEnvironment


def main():
    writers = 6
    readers = 2
    rounds = 50
    shared_key = "shared-account"

    with TestEnvironment(client_class=ConcurrentDatabaseClient) as env:
        env.database.put(shared_key, "initial-value")

        # Precompute every value a writer is allowed to publish.
        valid_values = {"initial-value"}

        for worker_id in range(writers):
            for sequence in range(rounds):
                valid_values.add(
                    f"writer-{worker_id}-value-{sequence}"
                )

        barrier = threading.Barrier(writers + readers)
        read_results = []
        write_results = []
        failures = []
        result_lock = threading.Lock()

        def writer(worker_id):
            barrier.wait()

            for sequence in range(rounds):
                value = f"writer-{worker_id}-value-{sequence}"

                try:
                    env.database.put(shared_key, value)

                    with result_lock:
                        write_results.append(value)

                except Exception as error:
                    with result_lock:
                        failures.append(str(error))
                    raise

        def reader(worker_id):
            barrier.wait()

            for _ in range(rounds * 2):
                try:
                    value = env.database.get(shared_key)

                    with result_lock:
                        read_results.append(value)

                    if value not in valid_values:
                        raise AssertionError(
                            f"Unexpected read value: {value!r}"
                        )

                except Exception as error:
                    with result_lock:
                        failures.append(str(error))
                    raise

        print("\n--- CONCURRENT READ/WRITE TEST ---")
        print("Writers:", writers)
        print("Readers:", readers)
        print("Writes per writer:", rounds)

        start = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=writers + readers
        ) as executor:
            futures = []

            for worker_id in range(writers):
                futures.append(
                    executor.submit(writer, worker_id)
                )

            for worker_id in range(readers):
                futures.append(
                    executor.submit(reader, worker_id)
                )

            for future in futures:
                future.result()

        elapsed = time.perf_counter() - start

        final_value = env.database.get(shared_key)

        total_writes = writers * rounds
        total_reads = readers * rounds * 2

        print("\n--- RESULTS ---")
        print("Successful writes:", len(write_results))
        print("Successful reads:", len(read_results))
        print("Invalid outcomes:", len(failures))
        print("Elapsed seconds:", round(elapsed, 4))
        print("Final value:", final_value)

        assert len(write_results) == total_writes
        assert len(read_results) == total_reads
        assert not failures
        assert final_value in valid_values

        print("\nCONCURRENT READ/WRITE TEST PASSED!")


if __name__ == "__main__":
    main()
