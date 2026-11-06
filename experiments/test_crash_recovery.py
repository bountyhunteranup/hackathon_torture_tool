from pathlib import Path
from tempfile import mkstemp
import os

from torture.controller import ProcessController
from torture.client import DatabaseClient
from torture.runner import TortureRunner
from torture.verifier import Verifier
from torture.recovery import RecoveryManager


# Locate the Go executable.
engine = (
    Path.home()
    / "Projects/Cosmic_Misfit/kvdb/kvdb-macos"
)

# Create a unique disposable database path.
fd, db_path = mkstemp(
    prefix="crash-test-",
    suffix=".db",
    dir=Path("logs").resolve()
)
os.close(fd)
os.unlink(db_path)

command = [
    str(engine),
    db_path,
    "serve",
    "127.0.0.1:8080"
]

controller = ProcessController(command)

database = DatabaseClient()

recovery = RecoveryManager(
    controller,
    "http://127.0.0.1:8080"
)

try:
    print("--- STARTING DATABASE ---")

    controller.start()
    recovery.wait_until_ready()

    runner = TortureRunner(database)

    print("\n--- EXECUTING WORKLOAD ---")

    runner.put("balance", "500")
    runner.put("account", "1000")
    runner.put("balance", "900")
    runner.delete("account")

    print("Oracle:", runner.oracle.expected_state)

    print("\n--- VERIFYING BEFORE CRASH ---")

    verifier = Verifier(database, runner.oracle)
    assert verifier.verify()

    print("\n--- INJECTING CRASH ---")

    controller.kill()

    print("\n--- RESTARTING DATABASE ---")

    recovery.restart()

    print("\n--- VERIFYING AFTER RECOVERY ---")

    assert verifier.verify()

    print("\nCRASH RECOVERY TEST PASSED!")

finally:
    if controller.is_running():
        controller.kill()

    print("\nDatabase process cleaned up.")
    print("Test database preserved at:", db_path)