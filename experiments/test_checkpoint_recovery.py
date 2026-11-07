
from torture.environment import TestEnvironment
import struct


MAGIC = b"BDVK"
FRAME_HEADER_SIZE = 12
CHECKPOINT_KIND = 3


def crc32c(data):
    """Calculate CRC32C using the Castagnoli polynomial."""
    crc = 0xFFFFFFFF

    for byte in data:
        crc ^= byte

        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x82F63B78
            else:
                crc >>= 1

    return crc ^ 0xFFFFFFFF


def find_checkpoints(data):
    """Scan database frames and return valid checkpoint offsets."""

    checkpoints = []
    offset = 8  # Database file header

    while offset + FRAME_HEADER_SIZE <= len(data):

        magic = data[offset:offset + 4]

        if magic != MAGIC:
            break

        body_length = struct.unpack_from(
            "<I", data, offset + 4
        )[0]

        stored_crc = struct.unpack_from(
            "<I", data, offset + 8
        )[0]

        body_start = offset + FRAME_HEADER_SIZE
        body_end = body_start + body_length

        if body_end > len(data):
            break

        body = data[body_start:body_end]

        calculated_crc = crc32c(body)

        if stored_crc != calculated_crc:
            break

        # Checkpoint body:
        # txnID(8) + opCount(4) + kind(1) + entryCount(4)
        if (
            len(body) >= 17
            and body[8:12] == b"\x00\x00\x00\x00"
            and body[12] == CHECKPOINT_KIND
        ):
            checkpoints.append(offset)

        offset = body_end

    return checkpoints


def main():

    with TestEnvironment() as env:

        print("\n--- PHASE 1: GENERATE CHECKPOINT WORKLOAD ---")

        operations = [
            {
                "type": "PUT",
                "key": f"ckpt-{i:05d}",
                "value": "v" * 64
            }
            for i in range(10_000)
        ]

        print("Operations prepared:", len(operations))

        # One atomic database batch triggers the 10,000-op threshold.
        assert env.database.batch(operations) == 204

        print("10,000 operations acknowledged")

        print("\n--- PHASE 2: VERIFY CHECKPOINT EXISTS ---")

        env.controller.stop()

        data = env.db_path.read_bytes()

        checkpoints = find_checkpoints(data)

        print("Database file size:", len(data))
        print("Valid checkpoint offsets:", checkpoints)

        assert checkpoints, "No valid checkpoint found!"

        checkpoint_offset = checkpoints[-1]

        print("Latest checkpoint offset:", checkpoint_offset)

        print("\n--- PHASE 3: WRITE AFTER CHECKPOINT ---")

        # Start the database again.
        env.restart()

        assert env.database.put(
            "post-checkpoint", "new-record"
        ) == 204

        # Overwrite an existing key.
        assert env.database.put(
            "ckpt-00000", "overwritten"
        ) == 204

        # Delete another existing key.
        assert env.database.delete(
            "ckpt-00001"
        ) == 204

        print("Post-checkpoint PUT, overwrite and DELETE completed")

        # Capture expected state independently.
        expected = {
            f"ckpt-{i:05d}": "v" * 64
            for i in range(10_000)
        }

        expected["post-checkpoint"] = "new-record"
        expected["ckpt-00000"] = "overwritten"
        del expected["ckpt-00001"]

        print("\n--- PHASE 4: RESTART AND VERIFY RECOVERY ---")

        env.controller.stop()
        env.restart()

        actual = env.database.dump()

        print("Expected key count:", len(expected))
        print("Actual key count:", len(actual))

        assert actual == expected, (
            "Checkpoint recovery mismatch!"
        )

        print("Checkpoint state and subsequent transactions verified")

        print("\n--- PHASE 5: VERIFY NEW WRITE DURABILITY ---")

        assert env.database.put(
            "final-record", "durable"
        ) == 204

        env.controller.stop()
        env.restart()

        assert env.database.get("final-record") == "durable"
        assert env.database.get("post-checkpoint") == "new-record"
        assert env.database.get("ckpt-00001") is None

        print("\nCHECKPOINT RECOVERY TEST PASSED!")


if __name__ == "__main__":
    main()
