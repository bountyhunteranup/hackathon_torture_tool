"""Test atomic recovery of a BATCH request interrupted by a crash."""

from torture.environment import TestEnvironment


def main():
    print("========== IN-FLIGHT BATCH CRASH TEST ==========")

    environment = TestEnvironment()

    baseline = {
        "stable:record": "must-survive",
    }

    batch_operations = [
        ("batch:A", "value-A"),
        ("batch:B", "value-B"),
        ("batch:C", "value-C"),
    ]

    try:
        # 1. Start the database and establish acknowledged baseline data.
        environment.start()
        database = environment.database

        print("\n--- WRITING BASELINE ---")

        for key, value in baseline.items():
            database.put(key, value)

        print("Baseline acknowledged.")

        # 2. Construct one BATCH request using the next request ID.
        request_id = database.request_id + 1

        batch_parts = []

        for key, value in batch_operations:
            batch_parts.extend(["put", key, value])

        request = (
            f"{request_id} batch "
            + " ; ".join(batch_parts)
            + "\n"
        )

        # 3. Send the request without observing its response.
        print("\n--- SENDING IN-FLIGHT BATCH ---")

        process = environment.controller.process

        if process is None or process.stdin is None:
            raise RuntimeError("Database process stdin is unavailable")

        process.stdin.write(request)
        process.stdin.flush()

        print("Batch sent. Response deliberately not observed.")

        # 4. Abruptly terminate the database.
        print("\n--- KILLING DATABASE ---")

        environment.controller.kill()

        # 5. Restart using the same database file.
        print("\n--- RESTARTING DATABASE ---")

        database = environment.restart()

        # 6. Verify baseline durability.
        print("\n--- VERIFYING RECOVERED STATE ---")

        for key, expected in baseline.items():
            actual = database.get(key)

            assert actual == expected, (
                f"Baseline data lost: {key}: "
                f"expected={expected!r}, actual={actual!r}"
            )

        # 7. Verify the uncertain batch was entirely applied or absent.
        recovered_batch = {
            key: database.get(key)
            for key, _ in batch_operations
        }

        print("Recovered batch state:", recovered_batch)

        all_present = all(
            recovered_batch[key] == value
            for key, value in batch_operations
        )

        all_absent = all(
            recovered_batch[key] is None
            for key, _ in batch_operations
        )

        assert all_present or all_absent, (
            "PARTIAL BATCH RECOVERY DETECTED: "
            f"{recovered_batch}"
        )

        print("\nIN-FLIGHT BATCH CRASH TEST PASSED!")

        if all_present:
            print("The entire uncertain batch was recovered.")
        else:
            print("The entire uncertain batch was absent.")

        print("The acknowledged baseline survived.")

    finally:
        environment.stop()
        print("\nDatabase:", environment.db_path)


if __name__ == "__main__":
    main()