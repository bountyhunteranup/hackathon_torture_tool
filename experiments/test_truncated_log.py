from torture.environment import TestEnvironment
from torture.runner import TortureRunner


def main():
    with TestEnvironment() as env:
        runner = TortureRunner(
            env.database,
            history=env.history
        )

        print("\n--- PHASE 1: BASELINE ---")
        assert runner.put("baseline", "safe")
        assert env.database.get("baseline") == "safe"

        # Stop the database before modifying its storage.
        env.controller.stop()

        print("\n--- PHASE 2: INJECT TRUNCATED RECORD ---")

        # A KVDB frame starts with magic, body length, and CRC32C. The body
        # here is deliberately incomplete, so recovery should discard it.
        #
        # This frame claims a 5-byte key and 5-byte value,
        # but provides only 2 bytes of key data.
        incomplete_record = (
            b"KVDB"
            + (24).to_bytes(4, "little")
            + b"\x00\x00\x00\x00"
            + b"partial"
        )

        with env.db_path.open("ab") as file:
            file.write(incomplete_record)

        print("Injected incomplete record:", len(incomplete_record), "bytes")

        print("\n--- PHASE 3: RESTART AND WRITE ---")
        env.restart()

        assert env.database.get("baseline") == "safe"
        assert env.database.put("after-corruption", "must-survive") == 204

        print("New write acknowledged")

        print("\n--- PHASE 4: RESTART AGAIN ---")
        env.controller.stop()
        env.restart()

        actual = env.database.get("after-corruption")
        expected = "must-survive"

        print("Expected:", expected)
        print("Actual:", actual)

        assert actual == expected, (
            "POTENTIAL STORAGE RECOVERY BUG: "
            "acknowledged write disappeared after restart"
        )

        print("\nTRUNCATED LOG RECOVERY TEST PASSED!")


if __name__ == "__main__":
    main()
