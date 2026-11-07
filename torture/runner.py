
import time

from torture.client import DatabaseRejected, OutcomeUnknown
from torture.oracle import Oracle
from torture.history import OperationHistory


class TortureRunner:

    def __init__(self, database, history=None):
        self.database = database
        self.oracle = Oracle()
        self.history = history or OperationHistory()
        self.operations = 0

    def _execute_recorded(self, operation, action, verifier=None):

        start_time = time.perf_counter()

        try:
            result = action()

        except Exception as error:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if isinstance(error, DatabaseRejected):
                outcome = "REJECTED"
            elif isinstance(error, OutcomeUnknown):
                outcome = "UNKNOWN"
            else:
                outcome = "FAILED"

            self.history.record(
                operation,
                outcome=outcome,
                verification="NOT_RUN",
                duration_ms=duration_ms,
                error=str(error)
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        outcome = "ACKNOWLEDGED"

        if operation["type"] == "GET" and result is None:
            outcome = "NOT_FOUND"

        verification = "NOT_CHECKED"
        verification_error = None

        if verifier is not None:
            try:
                verifier(result)
                verification = "PASSED"

            except AssertionError as error:
                verification = "FAILED"
                verification_error = str(error)

        self.history.record(
            operation,
            outcome=outcome,
            response=result,
            verification=verification,
            duration_ms=duration_ms,
            error=verification_error
        )

        if verification == "FAILED":
            raise AssertionError(verification_error)

        return result

    def put(self, key, value):

        operation = {
            "type": "PUT",
            "key": key,
            "value": value
        }

        def verify_status(status):
            if status != 204:
                raise AssertionError(
                    f"Unexpected PUT status: {status}"
                )

        self._execute_recorded(
            operation,
            lambda: self.database.put(key, value),
            verifier=verify_status
        )

        self.oracle.put(key, value)
        self.operations += 1

        return True

    def get(self, key):

        operation = {
            "type": "GET",
            "key": key
        }

        expected = self.oracle.get(key)

        def verify_result(actual):
            if actual != expected:
                raise AssertionError(
                    f"GET mismatch for {key}: "
                    f"expected={expected}, actual={actual}"
                )

        actual = self._execute_recorded(
            operation,
            lambda: self.database.get(key),
            verifier=verify_result
        )

        self.operations += 1
        return actual

    def delete(self, key):

        operation = {
            "type": "DELETE",
            "key": key
        }

        def verify_status(status):
            if status != 204:
                raise AssertionError(
                    f"Unexpected DELETE status: {status}"
                )

        self._execute_recorded(
            operation,
            lambda: self.database.delete(key),
            verifier=verify_status
        )

        self.oracle.delete(key)
        self.operations += 1

        return True
    def batch(self, operations):

        # Validate and compute the prospective Oracle state before sending.
        # This keeps malformed requests from reaching the database and makes
        # the eventual state change atomic from the runner's point of view.
        next_oracle = Oracle()
        next_oracle.expected_state = self.oracle.expected_state.copy()
        next_oracle.known_keys = self.oracle.known_keys.copy()
        next_oracle.apply_batch(operations)

        operation = {
            "type": "BATCH",
            "operations": [dict(item) for item in operations]
        }

        def verify_status(status):
            if status != 204:
                raise AssertionError(
                    f"Unexpected BATCH status: {status}"
                )

        # First, execute the complete batch against the database.
        self._execute_recorded(
            operation,
            lambda: self.database.batch(operation["operations"]),
            verifier=verify_status
        )

        # Only update the Oracle after database acknowledgement.
        self.oracle = next_oracle

        # Count individual database operations, not batch requests.
        self.operations += len(operations)

        return True

    def execute(self, operation):

        operation_type = operation["type"]

        if operation_type == "PUT":
            return self.put(operation["key"], operation["value"])

        elif operation_type == "GET":
            return self.get(operation["key"])

        elif operation_type == "DELETE":
            return self.delete(operation["key"])

        elif operation_type == "BATCH":
            return self.batch(operation["operations"])

        else:
            raise ValueError(f"Unknown operation: {operation_type}")
