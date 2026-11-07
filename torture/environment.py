
import os

from pathlib import Path
from tempfile import mkstemp

from torture.controller import ProcessController
from torture.client import DatabaseClient
from torture.history import OperationHistory


class TestEnvironment:
    __test__ = False

    def __init__(self, engine_path=None, client_class=DatabaseClient, extra_env=None):
        self.engine_path = (
            Path(engine_path)
            if engine_path
            else Path.home() / "Projects/Cosmic_Misfit/kvdb/kvdb-macos"
        )

        self.client_class = client_class
        self.extra_env = extra_env or {}

        self.log_dir = Path("logs").resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self._create_database_file()
        self.history_path = self._create_history_file()

        self.controller = ProcessController(
            [
                str(self.engine_path),
                "serve",
                str(self.db_path),
            ],
            extra_env=self.extra_env,
        )

        self.history = OperationHistory(str(self.history_path))
        self.database = None

    def _create_database_file(self):
        fd, path = mkstemp(
            prefix="campaign-",
            suffix=".db",
            dir=self.log_dir,
        )
        os.close(fd)
        os.unlink(path)
        return Path(path)

    def _create_history_file(self):
        fd, path = mkstemp(
            prefix="campaign-",
            suffix=".jsonl",
            dir=self.log_dir,
        )
        os.close(fd)
        return Path(path)

    def start(self):
        if not self.engine_path.is_file():
            raise FileNotFoundError(self.engine_path)

        self.controller.start()

        try:
            self.database = self.client_class(
                self.controller.process,
                self.engine_path,
                self.db_path,
            )
        except Exception:
            self.controller.stop()
            raise

        print("Test environment ready!")
        print("Database:", self.db_path)
        print("History:", self.history_path)

        return self

    def restart(self):
        """Start a fresh server process and reconnect the line client."""
        self.controller.start()

        try:
            self.database = self.client_class(
                self.controller.process,
                self.engine_path,
                self.db_path,
            )
        except Exception:
            self.controller.stop()
            raise

        return self.database

    def stop(self):
        self.controller.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        print("Test environment closed.")
