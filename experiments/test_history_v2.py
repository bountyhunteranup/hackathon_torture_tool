
from pathlib import Path
from tempfile import TemporaryDirectory

from torture.history import OperationHistory
from torture.runner import TortureRunner


class FakeDatabase:

    def put(self, key, value):
        return 204

    def get(self, key):
        return "WRONG_VALUE"


with TemporaryDirectory() as directory:

    history_path = Path(directory) / "test.jsonl"

    history = OperationHistory(str(history_path))
    runner = TortureRunner(FakeDatabase(), history)

    runner.put("apple", "red")

    try:
        runner.get("apple")
    except AssertionError as error:
        print("Detected incorrect GET:", error)

    record = history.records[-1]

    print("Protocol outcome:", record["outcome"])
    print("Actual response:", record["response"])
    print("Verification:", record["verification"])

    assert record["outcome"] == "ACKNOWLEDGED"
    assert record["response"] == "WRONG_VALUE"
    assert record["verification"] == "FAILED"

    print("NEGATIVE TEST PASSED")
