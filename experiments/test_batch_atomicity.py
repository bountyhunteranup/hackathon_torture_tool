
from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.client import DatabaseRejected


def main():

    environment = TestEnvironment()
    environment.start()

    try:
        runner = TortureRunner(
            environment.database,
            environment.history
        )

        print("\n--- STEP 1: ESTABLISH BASELINE ---")

        runner.put("existing-key", "original-value")

        baseline_database = environment.database.dump()
        baseline_oracle = runner.oracle.expected_state.copy()

        print("Baseline database:", baseline_database)

        print("\n--- STEP 2: CONSTRUCT ADVERSARIAL BATCH ---")

        operations = [
            {
                "type": "PUT",
                "key": "attack-key",
                "value": "compromised"
            },
            {
                "type": "DELETE",
                "key": "existing-key"
            },
            {
                "type": "PUT",
                "key": "x" * 1025,
                "value": "invalid"
            }
        ]

        print("Batch contains:", len(operations), "operations")

        print("\n--- STEP 3: EXECUTE BATCH ---")

        try:
            runner.batch(operations)
            raise AssertionError(
                "Database unexpectedly accepted invalid batch!"
            )

        except DatabaseRejected as error:
            print("Database correctly rejected batch:", error)

        print("\n--- STEP 4: VERIFY DATABASE STATE ---")

        actual_database = environment.database.dump()

        if actual_database != baseline_database:
            raise AssertionError(
                "ATOMICITY VIOLATION: Database partially changed!"
            )

        print("Database state unchanged.")

        print("\n--- STEP 5: VERIFY ORACLE STATE ---")

        if runner.oracle.expected_state != baseline_oracle:
            raise AssertionError(
                "ORACLE VIOLATION: Expected state changed!"
            )

        print("Oracle state unchanged.")

        print("\nBATCH ATOMICITY TEST PASSED!")

    finally:
        environment.stop()


if __name__ == "__main__":
    main()
