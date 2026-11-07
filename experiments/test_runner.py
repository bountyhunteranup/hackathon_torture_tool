
from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.verifier import Verifier


def main():
    print("========== RUNNER INTEGRATION TEST ==========")

    # Start a real Go database and connect the Python client.
    with TestEnvironment() as environment:

        runner = TortureRunner(
            environment.database,
            environment.history
        )

        print("\n--- INSERTING DATA ---")

        runner.put("apple", "100")
        runner.put("banana", "200")
        runner.put("mango", "300")

        assert runner.oracle.expected_state == {
            "apple": "100",
            "banana": "200",
            "mango": "300"
        }

        print("Oracle:", runner.oracle.expected_state)

        print("\n--- UPDATING DATA ---")

        runner.put("banana", "900")

        assert runner.oracle.get("banana") == "900"

        print("Oracle:", runner.oracle.expected_state)

        print("\n--- READING DATA ---")

        assert runner.get("apple") == "100"
        assert runner.get("banana") == "900"

        print("Apple:", runner.oracle.get("apple"))
        print("Banana:", runner.oracle.get("banana"))

        print("\n--- DELETING DATA ---")

        runner.delete("apple")

        assert runner.oracle.get("apple") is None

        print("Oracle:", runner.oracle.expected_state)

        print("\n--- VERIFYING DELETION ---")

        assert runner.get("apple") is None

        print("\nIndividual operations:", runner.operations)

        print("\n--- VERIFYING DATABASE AGAINST ORACLE ---")

        verifier = Verifier(environment.database, runner.oracle)
        assert verifier.verify_full_state()

        print("\n--- VERIFYING HISTORY ---")

        assert len(environment.history.records) == runner.operations

        print("History records:", len(environment.history.records))

    print("\nRUNNER INTEGRATION TEST PASSED!")


if __name__ == "__main__":
    main()
