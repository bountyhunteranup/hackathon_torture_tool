from torture.environment import TestEnvironment
from torture.concurrency import ConcurrencyEngine
from torture.benchmark import BenchmarkAnalyzer


with TestEnvironment() as environment:

    engine = ConcurrencyEngine(
        base_url=environment.base_url,
        history=environment.history,
        workers=4,
        operations_per_worker=500,
        seed=42
    )

    execution = engine.run()

    analyzer = BenchmarkAnalyzer()

    report = analyzer.analyze(
        results=execution["results"],
        elapsed_seconds=execution["elapsed_seconds"],
        workers=execution["workers"]
    )

    analyzer.display(report)

    print("\nBENCHMARK TEST COMPLETED!")