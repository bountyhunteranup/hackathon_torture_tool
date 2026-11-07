"""Verify that a missing engine reply cannot hang a campaign indefinitely."""

import subprocess
import sys

from torture.client import DatabaseClient, OutcomeUnknown, RequestTimeout


process = subprocess.Popen(
    [sys.executable, "-c", "import sys; list(sys.stdin)"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)
client = DatabaseClient(
    process,
    engine_path="unused",
    db_path="unused",
    request_timeout=0.1
)

try:
    try:
        client.put("key", "value")
    except RequestTimeout:
        pass
    else:
        raise AssertionError("Client did not time out")

    try:
        client.put("later", "value")
    except OutcomeUnknown:
        pass
    else:
        raise AssertionError("Client reused a timed-out connection")

    print("CLIENT TIMEOUT TEST PASSED")
finally:
    process.stdin.close()
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)
