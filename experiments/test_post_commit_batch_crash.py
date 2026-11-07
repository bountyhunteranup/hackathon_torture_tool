
from torture.environment import TestEnvironment


def main():
    print("========== POST-COMMIT BATCH CRASH TEST ==========")

    environment = TestEnvironment(
        extra_env={
            "KVDB_CRASH_AFTER_BATCH_COMMIT": "1"
        }
    )

    operations = [
        ("batch:A", "value-A"),
        ("batch:B", "value-B"),
        ("batch:C", "value-C"),
    ]

    try:
        environment.start()

        database = environment.database
        process = environment.controller.process

        # Send one batch directly, without waiting for its ACK.
        request_id = database.request_id + 1

        batch_commands = [
            f"put {key} {value}"
            for key, value in operations
        ]

        request = (
            f"{request_id} batch "
            + " ; ".join(batch_commands)
            + "\n"
        )

        print("\n--- SENDING BATCH ---")

        process.stdin.write(request)
        process.stdin.flush()

        # The Go test hook should terminate the process after commit.
        exit_code = process.wait(timeout=10)

        print("Database exit code:", exit_code)

        if exit_code != 86:
            raise AssertionError(
                f"Expected controlled crash exit 86, got {exit_code}"
            )

        print("Controlled post-commit crash confirmed.")

        # Disable the hook before restarting the database.
        environment.controller.extra_env = {}

        print("\n--- RESTARTING DATABASE ---")

        database = environment.restart()

        print("\n--- VERIFYING RECOVERED BATCH ---")

        recovered = {
            key: database.get(key)
            for key, _ in operations
        }

        print("Recovered state:", recovered)

        expected = dict(operations)

        if recovered != expected:
            raise AssertionError(
                f"Committed batch was not fully recovered: {recovered}"
            )

        print("\nPOST-COMMIT BATCH CRASH TEST PASSED!")

    finally:
        environment.stop()
        print("Database:", environment.db_path)


if __name__ == "__main__":
    main()
