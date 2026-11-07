from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.verifier import Verifier


with TestEnvironment() as environment:

    runner = TortureRunner(environment.database)

    key = "critical-account"

    values = [
        "100",
        "200",
        "300",
        "400",
        "500",
        "900"
    ]

    print("\n--- TESTING REPEATED OVERWRITES ---")

    for value in values:
        runner.put(key, value)
        print(f"PUT {key} = {value}")

    print("\n--- VERIFYING BEFORE RESTART ---")

    verifier = Verifier(
        environment.database,
        runner.oracle
    )

    assert verifier.verify()

    print("\n--- CRASHING DATABASE ---")

    environment.controller.kill()

    print("\n--- RESTARTING DATABASE ---")

    environment.restart()

    print("\n--- VERIFYING AFTER RESTART ---")

    verifier = Verifier(
        environment.database,
        runner.oracle
    )

    actual = environment.database.get(key)

    expected = values[-1]

    print("Expected:", expected)
    print("Actual:", actual)

    assert actual == expected, (
        f"Overwrite recovery failed: "
        f"expected {expected}, got {actual}"
    )

    assert verifier.verify()

    print("\nOVERWRITE RECOVERY TEST PASSED!")
