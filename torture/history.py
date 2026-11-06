import json
import threading

from datetime import datetime, timezone
from pathlib import Path


class OperationHistory:

    def __init__(self, log_path="logs/operations.jsonl"):
        self.lock = threading.Lock()
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.operation_id = 0
        self.records = []

    def record(self, operation, outcome, error=None):

        with self.lock:
            self.operation_id += 1

            entry = {
                "operation_id": self.operation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": operation["type"],
                "key": operation["key"],
                "value": operation.get("value"),
                "outcome": outcome,
                "error": error
            }

            self.records.append(entry)

            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry) + "\n")

            return entry