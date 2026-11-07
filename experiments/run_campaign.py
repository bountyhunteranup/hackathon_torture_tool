
from torture.environment import TestEnvironment
from torture.generator import WorkloadGenerator
from torture.runner import TortureRunner
from torture.verifier import Verifier
from torture.report import CampaignReport


SEED = 20261107
OPERATION_COUNT = 100


def main():
    print("========== KILL-IT CAMPAIGN ==========")
    print("Seed:", SEED)
    print("Operations:", OPERATION_COUNT)

    environment = TestEnvironment()
    runner = None
    execution_error = None
    verification_passed = False

    try:
        environment.start()

        generator = WorkloadGenerator(
            seed=SEED,
            keyspace=20,
        )

        runner = TortureRunner(
            environment.database,
            environment.history,
        )

        operations = generator.generate(OPERATION_COUNT)

        for number, operation in enumerate(operations, start=1):
            runner.execute(operation)

            if number % 20 == 0:
                print(f"Completed {number}/{OPERATION_COUNT}")

        print("\nWorkload completed.")

    except Exception as error:
        execution_error = error
        print(f"\nCAMPAIGN EXECUTION FAILED: {error}")

    finally:
        try:
            environment.stop()
        except Exception as error:
            if execution_error is None:
                execution_error = error
            print(f"\nDATABASE SHUTDOWN FAILED: {error}")

    if runner is not None and execution_error is None:
        try:
            print("\nChecking complete database state...")

            verifier = Verifier(
                environment.database,
                runner.oracle,
            )

            verification_passed = verifier.verify_full_state()

        except Exception as error:
            execution_error = error
            print(f"\nVERIFICATION ERROR: {error}")

    print("\nGenerating campaign report...")

    try:
        report = CampaignReport(environment.history_path)
        report.load()
        report.display()
    except Exception as error:
        execution_error = execution_error or error
        print(f"\nREPORT GENERATION FAILED: {error}")

    print("\nDatabase file:", environment.db_path)
    print("History file:", environment.history_path)

    if execution_error is not None:
        raise SystemExit(f"CAMPAIGN FAILED: {execution_error}")

    if not verification_passed:
        raise SystemExit("CAMPAIGN FAILED: Final state verification failed.")

    print("\nCAMPAIGN PASSED!")


if __name__ == "__main__":
    main()
