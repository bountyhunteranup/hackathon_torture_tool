import urllib.error

from torture.oracle import Oracle
from torture.history import OperationHistory


class TortureRunner:

    def __init__(self, database, history=None):
        self.database = database
        self.oracle = Oracle()
        self.history = history or OperationHistory()
        self.operations = 0

    def _execute_recorded(self, operation, action):
        try:
            result = action()

        except urllib.error.HTTPError as error:
            self.history.record(
                operation,
                "REJECTED",
                error=str(error)
            )
            raise

        except (urllib.error.URLError, TimeoutError, OSError) as error:
            self.history.record(
                operation,
                "UNKNOWN",
                error=str(error)
            )
            raise

        except Exception as error:
            self.history.record(
                operation,
                "FAILED",
                error=str(error)
            )
            raise

        outcome = "ACKNOWLEDGED"

        if operation["type"] == "GET" and result is None:
            outcome = "NOT_FOUND"

        self.history.record(operation, outcome)
        return result

    def put(self, key, value):
        operation = {
            "type": "PUT",
            "key": key,
            "value": value
        }

        status = self._execute_recorded(
            operation,
            lambda: self.database.put(key, value)
        )

        if status == 204:
            self.oracle.put(key, value)
            self.operations += 1
            return True

        raise RuntimeError(f"Unexpected PUT status: {status}")

    def get(self, key):
        operation = {
            "type": "GET",
            "key": key
        }

        actual = self._execute_recorded(
            operation,
            lambda: self.database.get(key)
        )

        expected = self.oracle.get(key)

        if actual != expected:
            raise AssertionError(
                f"GET mismatch for {key}: "
                f"expected={expected}, actual={actual}"
            )

        self.operations += 1
        return actual

    def delete(self, key):
        operation = {
            "type": "DELETE",
            "key": key
        }

        status = self._execute_recorded(
            operation,
            lambda: self.database.delete(key)
        )

        if status == 204:
            self.oracle.delete(key)
            self.operations += 1
            return True

        raise RuntimeError(f"Unexpected DELETE status: {status}")

    def execute(self, operation):
        operation_type = operation["type"]
        key = operation["key"]

        if operation_type == "PUT":
            return self.put(key, operation["value"])

        elif operation_type == "GET":
            return self.get(key)

        elif operation_type == "DELETE":
            return self.delete(key)

        else:
            raise ValueError(f"Unknown operation: {operation_type}")