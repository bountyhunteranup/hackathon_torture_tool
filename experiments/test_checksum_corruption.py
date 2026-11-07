
from torture.environment import TestEnvironment
from torture.runner import TortureRunner


def main():
    with TestEnvironment() as env:
        runner = TortureRunner(
            env.database,
            history=env.history
        )

        print("\n--- PHASE 1: WRITE VALID RECORDS ---")

        print("\n--- PHASE 1: WRITE VALID RECORDS ---")

        print("BEFORE FIRST PUT")
        assert runner.put("safe-key", "safe-value")
        print("AFTER FIRST PUT")

        assert runner.put("corrupt-key", "original-value")
        print("AFTER SECOND PUT")

        env.controller.stop()
        
        print("DATABASE SIZE:", env.db_path.stat().st_size)
        print("DATABASE PATH AFTER STOP:", env.db_path.resolve())
        print("\n--- PHASE 2: CORRUPT SECOND FRAME ---")

        data = bytearray(env.db_path.read_bytes())

        # The database header occupies 8 bytes.
        first_frame_offset = 8

        # Read the first frame's body length.
        first_body_length = int.from_bytes(
            data[first_frame_offset + 4:first_frame_offset + 8],
            "little"
        )

        # Calculate the second frame's starting position.
        second_frame_offset = (
            first_frame_offset + 12 + first_body_length
        )

        # Verify that the second frame really exists.
        assert data[second_frame_offset:second_frame_offset + 4] == b"BDVK"

        second_body_offset = second_frame_offset + 12

        # Normal frame body:
        # txnID(8) + opCount(4) + type(1) + keyLen(2) + valueLen(4)
        key_length_offset = second_body_offset + 12 + 1

        key_length = int.from_bytes(
            data[key_length_offset:key_length_offset + 2],
            "little"
        )

        # Calculate the beginning of the value.
        value_offset = second_body_offset + 12 + 7 + key_length

        # Confirm that we are corrupting the expected record.
        key_offset = second_body_offset + 12 + 7
        key = bytes(data[key_offset:key_offset + key_length])

        assert key == b"corrupt-key", f"Unexpected key: {key!r}"

        # Flip one bit without updating the CRC32C checksum.
        data[value_offset] ^= 0x01

        env.db_path.write_bytes(data)

        print("Corrupted key:", key.decode())
        print("Corrupted byte offset:", value_offset)

        print("\n--- PHASE 3: RESTART AND VERIFY ---")

        env.restart()

        safe_value = env.database.get("safe-key")
        corrupt_value = env.database.get("corrupt-key")

        print("Safe record:", safe_value)
        print("Corrupted record:", corrupt_value)

        assert safe_value == "safe-value"
        assert corrupt_value is None

        print("\n--- PHASE 4: VERIFY PHYSICAL TRUNCATION ---")

        recovered_size = env.db_path.stat().st_size

        print("Recovered file size:", recovered_size)
        print("Expected file size:", second_frame_offset)

        assert recovered_size == second_frame_offset

        print("\n--- PHASE 5: VERIFY NEW WRITES ---")

        assert env.database.put(
            "recovered-key", "new-data"
        ) == 204

        env.controller.stop()
        env.restart()

        assert env.database.get("safe-key") == "safe-value"
        assert env.database.get("recovered-key") == "new-data"

        print("\nCHECKSUM CORRUPTION TEST PASSED!")


if __name__ == "__main__":
    main()
