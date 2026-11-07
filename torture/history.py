
import json
import threading
from copy import deepcopy

from datetime import datetime, timezone
from pathlib import Path


class OperationHistory:

    def __init__(self, log_path="logs/operations.jsonl"):
        self.lock = threading.Lock()
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.operation_id = 0
        self.records = []

    def record(
        self,
        operation,
        outcome,
        response=None,
        verification="NOT_CHECKED",
        duration_ms=None,
        error=None,
        started_at=None,
        completed_at=None
    ):

        with self.lock:
            next_operation_id = self.operation_id + 1

            entry = {
                "operation_id": next_operation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "started_at": started_at,
                "completed_at": completed_at,

                "type": operation["type"],
                "key": operation.get("key"),
                "request_value": operation.get("value"),
                "operations": deepcopy(operation.get("operations")),

                "response": response,
                "outcome": outcome,
                "verification": verification,

                "duration_ms": duration_ms,
                "error": error
            }

            serialized = json.dumps(entry)

            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(serialized + "\n")

            self.operation_id = next_operation_id
            self.records.append(entry)
            return entry
