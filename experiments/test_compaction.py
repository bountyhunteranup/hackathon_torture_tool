
from torture.environment import TestEnvironment
from torture.runner import TortureRunner


def main():
    with TestEnvironment() as env:
        runner = TortureRunner(
            env.database,
            history=env.history
        )

        print("\n--- PHASE 1: CREATE LIVE RECORDS ---")

        value = "A" * 4096

        for i in range(4):
            assert runner.put(f"live:{i}", value)

        assert runner.put("obsolete-key", value)
        assert runner.delete("obsolete-key")

        initial_size = env.db_path.stat().st_size

        print("Initial database size:", initial_size)

        print("\n--- PHASE 2: GENERATE OBSOLETE RECORDS ---")

        sizes = [initial_size]

        for i in range(12):
            assert runner.put("hot-key", f"version-{i}-" + value)

            current_size = env.db_path.stat().st_size
            sizes.append(current_size)

            print(
                f"Overwrite {i + 1:02d}: "
                f"{current_size} bytes"
            )

        print("\n--- PHASE 3: VERIFY COMPACTION ---")

        compaction_detected = any(
            sizes[i] < sizes[i - 1]
            for i in range(1, len(sizes))
        )

        final_size = env.db_path.stat().st_size

        print("Initial size:", initial_size)
        print("Final size:", final_size)
        print("Compaction detected:", compaction_detected)

        assert compaction_detected, (
            "Database did not demonstrate automatic compaction"
        )

        temp_path = env.db_path.with_name(
            env.db_path.name + ".compact.tmp"
        )

        assert not temp_path.exists(), (
            "Unexpected leftover compaction temporary file"
        )

        print("\n--- PHASE 4: VERIFY LIVE DATABASE STATE ---")

        for i in range(4):
            assert env.database.get(f"live:{i}") == value

        assert env.database.get("obsolete-key") is None

        expected_hot_value = "version-11-" + value

        assert env.database.get("hot-key") == expected_hot_value

        print("All live records verified")
        print("Deleted record remains absent")

        print("\n--- PHASE 5: VERIFY RESTART RECOVERY ---")

        env.controller.stop()
        env.restart()

        for i in range(4):
            assert env.database.get(f"live:{i}") == value

        assert env.database.get("obsolete-key") is None
        assert env.database.get("hot-key") == expected_hot_value

        print("\n--- PHASE 6: VERIFY NEW WRITES ---")

        assert env.database.put(
            "after-compaction", "durable"
        ) == 204

        env.controller.stop()
        env.restart()

        assert env.database.get("after-compaction") == "durable"

        print("\nCOMPACTION TEST PASSED!")


if __name__ == "__main__":
    main()
