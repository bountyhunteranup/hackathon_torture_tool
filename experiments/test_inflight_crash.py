
"""Test a write whose response is not observed before a process crash."""

from torture.environment import TestEnvironment


def main():
    print("========== IN-FLIGHT CRASH TEST ==========")

    environment = TestEnvironment()

    stable_key = "stable:record"
    uncertain_key = "uncertain:record"
    uncertain_value = "possibly-committed"

    try:
        # Start the real database.
        environment.start()
        database = environment.database

        # Establish a known, acknowledged baseline.
        print("\n--- WRITING BASELINE ---")

        database.put(stable_key, "must-survive")
        print("Baseline write acknowledged.")

        # Prepare a request ID that the client has not used yet.
        request_id = database.request_id + 1

        # Send the request directly, without waiting for its response.
        print("\n--- SENDING IN-FLIGHT REQUEST ---")

        process = environment.controller.process

        if process is None or process.stdin is None:
            raise RuntimeError("Database process stdin is unavailable")

        request = (
            f"{request_id} put {uncertain_key} {uncertain_value}\n"
        )

        process.stdin.write(request)
        process.stdin.flush()

        print("Request sent. Response deliberately not observed.")

        # Abruptly kill the process.
        print("\n--- KILLING DATABASE ---")

        environment.controller.kill()

        # Restart the same database file.
        print("\n--- RESTARTING DATABASE ---")

        database = environment.restart()

        # The acknowledged baseline must survive.
        print("\n--- CHECKING RECOVERED STATE ---")

        stable_actual = database.get(stable_key)

        assert stable_actual == "must-survive", (
            f"Baseline data lost: {stable_actual!r}"
        )

        # The uncertain write may or may not have committed.
        uncertain_actual = database.get(uncertain_key)

        print("Baseline:", stable_actual)
        print("Uncertain write:", uncertain_actual)

        assert uncertain_actual in (None, uncertain_value), (
            f"Unexpected recovered value: {uncertain_actual!r}"
        )

        print("\nIN-FLIGHT CRASH TEST PASSED!")
        print("The uncertain write was either fully present or absent.")
        print("The acknowledged baseline survived.")

    finally:
        environment.stop()
        print("\nDatabase:", environment.db_path)


if __name__ == "__main__":
    main()
