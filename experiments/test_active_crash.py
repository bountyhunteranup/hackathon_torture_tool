
"""Test whether acknowledged writes survive abrupt process termination."""

from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.verifier import Verifier


def main():
    print("========== CRASH DURABILITY TEST ==========")

    environment = TestEnvironment()

    try:
        # 1. Start the real database.
        environment.start()

        runner = TortureRunner(
            environment.database,
            environment.history
        )

        # 2. Perform writes that must survive the crash.
        print("\n--- WRITING ACKNOWLEDGED DATA ---")

        runner.put("user:1", "Anup")
        runner.put("user:2", "Engineer")
        runner.put("account:1", "5000")

        runner.batch([
            {"type": "PUT", "key": "session:1", "value": "active"},
            {"type": "PUT", "key": "session:2", "value": "inactive"},
            {"type": "DELETE", "key": "user:2"},
        ])

        expected = runner.oracle.expected_state.copy()

        print("Acknowledged operations:", runner.operations)
        print("Expected state:", expected)

        # 3. Kill the process without graceful shutdown.
        print("\n--- INJECTING ABRUPT CRASH ---")

        environment.controller.kill()

        assert not environment.controller.is_running()
        print("Database process is dead.")

        # 4. Restart using the same database file.
        print("\n--- RESTARTING DATABASE ---")

        environment.restart()

        # 5. Compare recovered state with the pre-crash Oracle.
        print("\n--- VERIFYING RECOVERED DATA ---")

        verifier = Verifier(environment.database, runner.oracle)
        assert verifier.verify()

        # Explicitly check the snapshot too.
        for key, expected_value in expected.items():
            actual_value = environment.database.get(key)
            assert actual_value == expected_value, (
                f"Recovery mismatch for {key}: "
                f"expected={expected_value!r}, actual={actual_value!r}"
            )

        print("\nACKNOWLEDGED WRITE DURABILITY PASSED!")

    finally:
        environment.stop()
        print("\nDatabase:", environment.db_path)
        print("History:", environment.history_path)


if __name__ == "__main__":
    main()
