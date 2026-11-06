import threading
import time

from torture.environment import TestEnvironment
from torture.generator import WorkloadGenerator
from torture.runner import TortureRunner
from torture.verifier import Verifier


def main():
    environment = TestEnvironment()

    worker_started = threading.Event()
    worker_errors = []

    generator = WorkloadGenerator(seed=42, keyspace=100)

    try:
        environment.start()

        runner = TortureRunner(
            environment.database,
            history=environment.history
        )

        def run_workload():
            worker_started.set()

            try:
                while True:
                    operation = generator.generate_operation()
                    runner.execute(operation)

            except Exception as error:
                worker_errors.append(error)

        worker = threading.Thread(target=run_workload)
        worker.start()

        if not worker_started.wait(timeout=5):
            raise TimeoutError("Worker did not start")

        time.sleep(0.1)

        print("\n--- CRASHING DATABASE DURING WORKLOAD ---")
        print("Acknowledged operations:", runner.operations)

        environment.controller.kill()

        worker.join(timeout=10)

        if worker.is_alive():
            raise RuntimeError("Worker did not stop after crash")

        print("\n--- CRASH RESULTS ---")
        print("Acknowledged:", runner.operations)
        print("Recorded:", len(environment.history.records))

        if worker_errors:
            print("Worker error:", repr(worker_errors[0]))

        print("\n--- RESTARTING DATABASE ---")
        environment.recovery.restart()

        print("\n--- VERIFYING RECOVERED STATE ---")

        verifier = Verifier(environment.database, runner.oracle)

        assert verifier.verify()

        print("\nACTIVE CRASH RECOVERY TEST PASSED!")

    finally:
        environment.stop()
        print("Database:", environment.db_path)
        print("History:", environment.history_path)


if __name__ == "__main__":
    main()