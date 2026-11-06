from torture.environment import TestEnvironment
from torture.generator import WorkloadGenerator
from torture.runner import TortureRunner
from torture.verifier import Verifier


with TestEnvironment() as environment:

    generator = WorkloadGenerator(
        seed=42,
        keyspace=20
    )

    workload = generator.generate(100)

    runner = TortureRunner(
        environment.database,
        history=environment.history
    )

    print("\n--- EXECUTING WORKLOAD ---")

    for operation in workload:
        runner.execute(operation)

    print("\n--- VERIFYING DATABASE ---")

    verifier = Verifier(
        environment.database,
        runner.oracle
    )

    assert verifier.verify()

    print("\n--- CAMPAIGN SUMMARY ---")
    print("Operations executed:", runner.operations)
    print("Operations recorded:", len(environment.history.records))
    print("Database:", environment.db_path)
    print("History:", environment.history_path)

    print("\nTEST CAMPAIGN PASSED!")