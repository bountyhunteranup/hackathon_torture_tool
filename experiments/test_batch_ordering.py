
from torture.environment import TestEnvironment
from torture.runner import TortureRunner


def main():

    environment = TestEnvironment()
    environment.start()

    try:
        runner = TortureRunner(
            environment.database,
            environment.history
        )

        print("\n--- TEST 1: PUT, PUT, DELETE ---")

        runner.batch([
            {"type": "PUT", "key": "apple", "value": "red"},
            {"type": "PUT", "key": "apple", "value": "green"},
            {"type": "DELETE", "key": "apple"}
        ])

        apple = environment.database.get("apple")

        if apple is not None:
            raise AssertionError(
                f"Ordering failure: expected apple to be absent, got {apple}"
            )

        print("Apple correctly deleted.")

        print("\n--- TEST 2: PUT, DELETE, PUT ---")

        runner.batch([
            {"type": "PUT", "key": "banana", "value": "yellow"},
            {"type": "DELETE", "key": "banana"},
            {"type": "PUT", "key": "banana", "value": "blue"}
        ])

        banana = environment.database.get("banana")

        if banana != "blue":
            raise AssertionError(
                f"Ordering failure: expected blue, got {banana}"
            )

        print("Banana correctly contains:", banana)

        print("\n--- TEST 3: VERIFY ORACLE ---")

        if runner.oracle.get("apple") is not None:
            raise AssertionError("Oracle incorrectly contains apple")

        if runner.oracle.get("banana") != "blue":
            raise AssertionError("Oracle has incorrect banana value")

        print("Oracle matches expected state.")

        print("\nBATCH ORDERING TEST PASSED!")

    finally:
        environment.stop()


if __name__ == "__main__":
    main()
