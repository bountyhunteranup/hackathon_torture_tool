"""Line-protocol client that safely matches out-of-order engine replies."""

import queue
import subprocess
import threading

from torture.client import (
    DatabaseClient,
    DatabaseRejected,
    DatabaseUnavailable,
    OutcomeUnknown,
    RequestTimeout,
)


class ConcurrentDatabaseClient:
    """Allow multiple in-flight requests, correlating each reply by ID.

    A timed-out request is reported as uncertain. Its pending slot is removed,
    but the connection remains usable because later replies carry their own
    request IDs and cannot be mistaken for another request's response.
    """

    def __init__(self, process, engine_path, db_path, request_timeout=10.0):
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")

        self.process = process
        self.engine_path = engine_path
        self.db_path = db_path
        self.request_timeout = request_timeout
        self.request_id = 0
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._closed = False
        self._reader = threading.Thread(
            target=self._read_responses,
            name="concurrent-database-response-reader",
            daemon=True,
        )
        self._reader.start()

    def _fail_pending(self, error):
        with self._pending_lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for response_queue in pending:
            response_queue.put(error)

    def _read_responses(self):
        try:
            for response in self.process.stdout:
                parts = response.rstrip("\r\n").split(" ", 2)
                if len(parts) < 2 or not parts[1].isdigit():
                    self._fail_pending(
                        OutcomeUnknown(f"Malformed response: {response!r}")
                    )
                    return

                with self._pending_lock:
                    response_queue = self._pending.get(int(parts[1]))

                # A timeout may have removed this request already. Its late
                # reply is safe to discard because IDs are never reused.
                if response_queue is None:
                    continue

                if parts[0] == "ERR":
                    response_queue.put(DatabaseRejected(response.strip()))
                else:
                    response_queue.put(
                        (parts[0], parts[2] if len(parts) > 2 else None)
                    )
        except (OSError, ValueError) as error:
            self._fail_pending(
                OutcomeUnknown(f"Error reading database responses: {error}")
            )
        finally:
            self._fail_pending(
                OutcomeUnknown("Database closed its output stream")
            )

    def _request(self, command):
        if self.process.poll() is not None:
            raise DatabaseUnavailable("Database process is not running")

        with self._pending_lock:
            if self._closed:
                raise OutcomeUnknown("Database connection is closed")
            self.request_id += 1
            request_id = self.request_id
            response_queue = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue

        try:
            with self._write_lock:
                self.process.stdin.write(f"{request_id} {command}\n")
                self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            uncertain = OutcomeUnknown(
                f"Request {request_id} may have been processed: {error}"
            )
            self._fail_pending(uncertain)
            raise uncertain from error

        try:
            result = response_queue.get(timeout=self.request_timeout)
        except queue.Empty as error:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise RequestTimeout(
                f"Timed out waiting for request {request_id}; "
                "the operation may have taken effect"
            ) from error

        if isinstance(result, BaseException):
            raise result
        return result

    def put(self, key, value):
        DatabaseClient._validate_key(key)
        DatabaseClient._validate_value(value)
        status, _ = self._request(f"put {key} {value}")
        if status != "ACK":
            raise RuntimeError(f"Unexpected PUT response: {status}")
        return 204

    def get(self, key):
        DatabaseClient._validate_key(key)
        status, value = self._request(f"get {key}")
        if status == "NOTFOUND":
            return None
        if status == "VAL":
            return value
        raise RuntimeError(f"Unexpected GET response: {status}")

    def delete(self, key):
        DatabaseClient._validate_key(key)
        status, _ = self._request(f"del {key}")
        if status != "ACK":
            raise RuntimeError(f"Unexpected DELETE response: {status}")
        return 204

    def batch(self, operations):
        if not isinstance(operations, (list, tuple)) or not operations:
            raise ValueError("Batch must contain at least one operation")

        parts = []
        for operation in operations:
            operation_type = operation["type"]
            key = operation["key"]
            DatabaseClient._validate_key(key)
            if ";" in key:
                raise ValueError("Invalid key for batch protocol")

            if operation_type == "PUT":
                value = operation["value"]
                DatabaseClient._validate_value(value)
                if ";" in value:
                    raise ValueError("Invalid value for batch protocol")
                parts.append(f"put {key} {value}")
            elif operation_type == "DELETE":
                parts.append(f"del {key}")
            else:
                raise ValueError(
                    f"Unsupported batch operation: {operation_type}"
                )

        status, _ = self._request("batch " + " ; ".join(parts))
        if status != "ACK":
            raise RuntimeError(f"Unexpected batch response: {status}")
        return 204

    def dump(self):
        result = subprocess.run(
            [str(self.engine_path), "dump", str(self.db_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        database = {}
        for line in result.stdout.splitlines():
            key, value = line.split("\t", 1)
            database[key] = value
        return database
