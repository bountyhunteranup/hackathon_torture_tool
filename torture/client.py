import subprocess
import queue
import threading


class DatabaseClientError(Exception):
    """Base class for errors raised by the line-protocol client."""


class DatabaseRejected(DatabaseClientError):
    """The server returned ERR, so it explicitly rejected the request."""


class DatabaseUnavailable(DatabaseClientError):
    """The server was already stopped before this request was sent."""


class OutcomeUnknown(DatabaseClientError):
    """The request may have been sent, but no reliable reply was received."""


class RequestTimeout(OutcomeUnknown):
    """The server did not reply before the configured deadline."""


class DatabaseClient:

    _EOF = object()

    def __init__(self, process, engine_path, db_path, request_timeout=10.0):
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        self.process = process
        self.engine_path = engine_path
        self.db_path = db_path
        self.request_id = 0
        self.request_timeout = request_timeout
        self._response_queue = queue.Queue()
        self._request_lock = threading.Lock()
        self._broken = False
        self._reader = threading.Thread(
            target=self._read_responses,
            name="database-response-reader",
            daemon=True
        )
        self._reader.start()

    def _read_responses(self):
        try:
            for response in self.process.stdout:
                self._response_queue.put(response)
        except (OSError, ValueError):
            pass
        finally:
            self._response_queue.put(self._EOF)

    @staticmethod
    def _validate_key(key):
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")
        if any(char in key for char in (" ", "\t", "\n", "\r")):
            raise ValueError("Key cannot contain whitespace")

    @staticmethod
    def _validate_value(value):
        if not isinstance(value, str):
            raise ValueError("Value must be a string")
        if "\n" in value or "\r" in value:
            raise ValueError("Value cannot contain newlines")

    def _request(self, command):
        with self._request_lock:
            if self._broken:
                raise OutcomeUnknown(
                    "Client cannot continue after an earlier uncertain request"
                )
            if self.process.poll() is not None:
                raise DatabaseUnavailable("Database process is not running")

            self.request_id += 1
            request_id = self.request_id

            try:
                self.process.stdin.write(f"{request_id} {command}\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                self._broken = True
                raise OutcomeUnknown(
                    f"Request {request_id} may have been processed: {error}"
                ) from error

            try:
                response = self._response_queue.get(
                    timeout=self.request_timeout
                )
            except queue.Empty as error:
                self._broken = True
                raise RequestTimeout(
                    f"Timed out waiting for request {request_id}; "
                    "the operation may have taken effect"
                ) from error

            if response is self._EOF:
                self._broken = True
                raise OutcomeUnknown(
                    f"Database closed output while awaiting request {request_id}"
                )

            parts = response.strip().split(" ", 2)

            if len(parts) < 2 or parts[1] != str(request_id):
                self._broken = True
                raise OutcomeUnknown(f"Unexpected response: {response!r}")

            status = parts[0]

            if status == "ERR":
                raise DatabaseRejected(response.strip())

            return status, parts[2] if len(parts) > 2 else None

    def put(self, key, value):
        self._validate_key(key)
        self._validate_value(value)
        status, _ = self._request(f"put {key} {value}")

        if status != "ACK":
            raise RuntimeError(f"Unexpected PUT response: {status}")

        return 204

    def get(self, key):
        self._validate_key(key)
        status, value = self._request(f"get {key}")

        if status == "NOTFOUND":
            return None

        if status == "VAL":
            return value

        raise RuntimeError(f"Unexpected GET response: {status}")

    def delete(self, key):
        self._validate_key(key)
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

            self._validate_key(key)

            if ";" in key:
                raise ValueError("Invalid key for batch protocol")

            if operation_type == "PUT":

                value = operation["value"]

                self._validate_value(value)

                if ";" in value:
                    raise ValueError("Invalid value for batch protocol")

                parts.append(f"put {key} {value}")

            elif operation_type == "DELETE":

                parts.append(f"del {key}")

            else:
                raise ValueError(
                    f"Unsupported batch operation: {operation_type}"
                )

        command = "batch " + " ; ".join(parts)

        status, _ = self._request(command)

        if status != "ACK":
            raise RuntimeError(f"Unexpected batch response: {status}")

        return 204
    def dump(self):
        result = subprocess.run(
            [str(self.engine_path), "dump", str(self.db_path)],
            capture_output=True,
            text=True,
            check=True
        )

        database = {}

        for line in result.stdout.splitlines():
            key, value = line.split("\t", 1)
            database[key] = value

        return database
