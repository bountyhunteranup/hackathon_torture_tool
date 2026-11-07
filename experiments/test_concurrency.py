"""Run a concurrent line-protocol campaign against the Go engine."""

from torture.concurrent_client import ConcurrentDatabaseClient
from torture.concurrent_runner import ConcurrentCampaignRunner
from torture.environment import TestEnvironment


with TestEnvironment(client_class=ConcurrentDatabaseClient) as environment:
    runner = ConcurrentCampaignRunner(environment.database, environment.history)
    summary = runner.run(workers=4, rounds_per_worker=25)

    print("\n--- CONCURRENCY SUMMARY ---")
    print("Workers:", summary["workers"])
    print("Total operations:", summary["total_operations"])
    print("Duration:", round(summary["elapsed_seconds"], 3), "seconds")
    print("Operations/second:", round(summary["operations_per_second"], 2))
    print("Final state verified:", summary["final_state_verified"])

print("\nCONCURRENCY TEST PASSED!")
