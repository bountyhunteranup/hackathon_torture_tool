"""Benchmark the current concurrent request path."""

from torture.benchmark import BenchmarkAnalyzer
from torture.concurrent_client import ConcurrentDatabaseClient
from torture.concurrent_runner import ConcurrentCampaignRunner
from torture.environment import TestEnvironment


with TestEnvironment(client_class=ConcurrentDatabaseClient) as environment:
    runner = ConcurrentCampaignRunner(environment.database, environment.history)
    execution = runner.run(workers=4, rounds_per_worker=125)

    analyzer = BenchmarkAnalyzer()
    report = analyzer.analyze(
        results=execution["results"],
        elapsed_seconds=execution["elapsed_seconds"],
        workers=execution["workers"],
    )
    analyzer.display(report)

    assert report["total_operations"] == 2000
    assert report["error_rate_percent"] == 0

print("\nBENCHMARK TEST COMPLETED!")
