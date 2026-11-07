"""Integration check for concurrent execution, verification, and history."""

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.concurrent_runner import ConcurrentCampaignRunner
from torture.environment import TestEnvironment


with TestEnvironment(client_class=ConcurrentDatabaseClient) as environment:
    runner = ConcurrentCampaignRunner(environment.database, environment.history)
    summary = runner.run(workers=8, rounds_per_worker=5)

    assert summary["total_operations"] == 160
    assert summary["final_state_verified"]
    assert len(environment.history.records) == 160
    assert all(
        record["verification"] == "PASSED"
        and record["started_at"]
        and record["completed_at"]
        for record in environment.history.records
    )

    print("CONCURRENT RUNNER TEST PASSED")
    print("Operations:", summary["total_operations"])
    print(f"Throughput: {summary['operations_per_second']:.1f} ops/s")
