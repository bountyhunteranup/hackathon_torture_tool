"""Check batch execution, Oracle updates, and rejected-batch history."""

from torture.client import DatabaseRejected
from torture.environment import TestEnvironment
from torture.runner import TortureRunner


def main():
    with TestEnvironment() as environment:
        runner = TortureRunner(environment.database, environment.history)
        database = environment.database

        print("\n--- VALID BATCH ---")
        runner.batch([
            {"type": "PUT", "key": "apple", "value": "red"},
            {"type": "PUT", "key": "banana", "value": "yellow"},
            {"type": "DELETE", "key": "apple"},
        ])

        assert database.get("apple") is None
        assert database.get("banana") == "yellow"
        assert runner.oracle.get("apple") is None
        assert runner.oracle.get("banana") == "yellow"
        assert runner.operations == 3
        print("Valid batch and Oracle state passed.")

        print("\n--- REJECTED BATCH ---")
        try:
            runner.batch([
                {"type": "PUT", "key": "cherry", "value": "green"},
                {"type": "PUT", "key": "k" * 1025, "value": "invalid"},
            ])
        except DatabaseRejected as error:
            print("Database rejected batch:", error)
        else:
            raise AssertionError("Invalid batch was accepted")

        assert database.get("cherry") is None
        assert runner.oracle.get("cherry") is None
        assert database.get("banana") == runner.oracle.get("banana") == "yellow"
        assert runner.operations == 3
        assert environment.history.records[-1]["outcome"] == "REJECTED"

        print("Rejected batch left the database and Oracle unchanged.")
        print("BATCH RUNNER TEST PASSED")


if __name__ == "__main__":
    main()
