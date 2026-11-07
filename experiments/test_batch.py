import sys
from pathlib import Path

# Support both `python -m experiments.test_batch` and running this file
# directly from an IDE, where Python otherwise searches from experiments/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from torture.environment import TestEnvironment
from torture.client import DatabaseRejected


environment = TestEnvironment()
environment.start()

try:
    db = environment.database

    # TEST 1: Valid batch
    print("\nTEST 1: Valid batch")

    db.batch([
        {"type": "PUT", "key": "apple", "value": "red"},
        {"type": "PUT", "key": "banana", "value": "yellow"},
        {"type": "DELETE", "key": "apple"}
    ])

    assert db.get("apple") is None
    assert db.get("banana") == "yellow"

    print("VALID BATCH PASSED")

    # TEST 2: Invalid batch
    print("\nTEST 2: Invalid batch")

    try:
        db.batch([
            {"type": "PUT", "key": "cherry", "value": "green"},
            {
                "type": "PUT",
                "key": "k" * 1025,
                "value": "invalid"
            }
        ])

        raise AssertionError("Invalid batch was accepted")

    except DatabaseRejected as error:
        print("Database rejected batch:", error)

    # Verify atomicity
    assert db.get("cherry") is None
    assert db.get("banana") == "yellow"

    print("ATOMICITY TEST PASSED")

finally:
    environment.stop()
