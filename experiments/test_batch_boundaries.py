
from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.client import DatabaseRejected, OutcomeUnknown


def main():

    environment = TestEnvironment()
    environment.start()

    try:
        runner = TortureRunner(
            environment.database,
            environment.history
        )

        print("\n--- TEST 1: MINIMUM BATCH ---")

        runner.batch([
            {"type": "PUT", "key": "minimum", "value": "valid"}
        ])

        assert runner.oracle.get("minimum") == "valid"
        print("One-operation batch accepted.")

        print("\n--- TEST 2: MAXIMUM BATCH ---")

        maximum_batch = [
            {
                "type": "PUT",
                "key": "maximum-key",
                "value": f"value-{i}"
            }
            for i in range(10000)
        ]

        runner.batch(maximum_batch)

        assert runner.oracle.get("maximum-key") == "value-9999"

        print("10,000-operation batch accepted.")
        print("Individual operations executed:", runner.operations)

        print("\n--- TEST 3: OVERSIZED BATCH ---")

        oracle_before = runner.oracle.expected_state.copy()
        database_before = environment.database.dump()

        oversized_batch = [
            {
                "type": "PUT",
                "key": "oversized-key",
                "value": "test"
            }
            for _ in range(10001)
        ]

        try:
            runner.batch(oversized_batch)

            raise AssertionError(
                "Database unexpectedly accepted 10,001 operations!"
            )

        except DatabaseRejected as error:
            print("10,001-operation batch rejected:", error)

        except OutcomeUnknown as error:
            raise AssertionError(
                "Outcome uncertain; cannot claim boundary test passed."
            ) from error

        assert runner.oracle.expected_state == oracle_before

        database_after = environment.database.dump()

        assert database_after == database_before

        print("Oracle unchanged.")
        print("Database unchanged.")

        print("\nBATCH BOUNDARY TEST PASSED!")

    finally:
        environment.stop()


if __name__ == "__main__":
    main()
