"""Verify acknowledged writes survive an abrupt process restart."""

from torture.environment import TestEnvironment
from torture.runner import TortureRunner
from torture.verifier import Verifier


def main():
    with TestEnvironment() as environment:
        runner = TortureRunner(environment.database, environment.history)
        runner.put("balance", "500")
        runner.put("account", "1000")
        runner.put("balance", "900")
        runner.delete("account")

        expected = runner.oracle.expected_state.copy()
        print("Expected before crash:", expected)

        environment.controller.kill()
        environment.restart()

        verifier = Verifier(environment.database, runner.oracle)
        assert verifier.verify_full_state()
        assert environment.database.dump() == expected

    print("\nCRASH RECOVERY TEST PASSED!")


if __name__ == "__main__":
    main()
