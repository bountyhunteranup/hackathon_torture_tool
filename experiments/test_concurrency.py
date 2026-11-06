from torture.environment import TestEnvironment
from torture.concurrency import ConcurrencyEngine


with TestEnvironment() as environment:

    engine = ConcurrencyEngine(
        base_url=environment.base_url,
        history=environment.history,
        workers=4,
        operations_per_worker=100,
        seed=42
    )

    summary = engine.run()

    print("\n--- CONCURRENCY SUMMARY ---")
    print("Workers:", summary["workers"])
    print("Total operations:", summary["total_operations"])
    print("Duration:", round(summary["elapsed_seconds"], 3), "seconds")
    print(
        "Operations/second:",
        round(summary["operations_per_second"], 2)
    )

    print("\n--- OUTCOMES ---")

    outcomes = {}

    for result in summary["results"]:
        outcome = result["outcome"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    for outcome, count in sorted(outcomes.items()):
        print(f"{outcome}: {count}")

    print("\nCONCURRENCY TEST COMPLETED!")