import socket
import os

from pathlib import Path
from tempfile import mkstemp

from torture.controller import ProcessController
from torture.client import DatabaseClient
from torture.history import OperationHistory
from torture.recovery import RecoveryManager


class TestEnvironment:

    def __init__(self, engine_path=None):
        self.engine_path = (
            Path(engine_path)
            if engine_path
            else Path.home() / "Projects/Cosmic_Misfit/kvdb/kvdb-macos"
        )

        self.log_dir = Path("logs").resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self._create_database_file()
        self.history_path = self._create_history_file()
        self.port = self._find_free_port()

        self.base_url = f"http://127.0.0.1:{self.port}"

        self.controller = ProcessController([
            str(self.engine_path),
            str(self.db_path),
            "serve",
            f"127.0.0.1:{self.port}"
        ])

        self.database = DatabaseClient(self.base_url)
        self.history = OperationHistory(str(self.history_path))

        self.recovery = RecoveryManager(
            self.controller,
            self.base_url
        )

    def _create_database_file(self):
        fd, path = mkstemp(
            prefix="campaign-",
            suffix=".db",
            dir=self.log_dir
        )
        os.close(fd)
        os.unlink(path)
        return Path(path)

    def _create_history_file(self):
        fd, path = mkstemp(
            prefix="campaign-",
            suffix=".jsonl",
            dir=self.log_dir
        )
        os.close(fd)
        return Path(path)

    def _find_free_port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def start(self):
        if not self.engine_path.is_file():
            raise FileNotFoundError(
                f"Database executable not found: {self.engine_path}"
            )

        self.controller.start()
        self.recovery.wait_until_ready()
        print("Test environment ready!")
        print("Database:", self.db_path)
        print("History:", self.history_path)
        print("Address:", self.base_url)

        return self

    def stop(self):
        if self.controller.is_running():
            self.controller.kill()

    def __enter__(self):
        try:
            return self.start()
        except Exception:
            self.stop()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        print("Test environment closed.")