
import argparse
import json
import os
import signal
import subprocess
import sys
import time

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"

EXPERIMENTS = {
    "correctness": [
        "experiments.run_campaign",
        "experiments.test_batch",
        "experiments.test_batch_atomicity",
        "experiments.test_batch_boundaries",
        "experiments.test_batch_ordering",
        "experiments.test_batch_runner",
        "experiments.test_full_verifier",
    ],
    "concurrency": [
        "experiments.test_concurrent_batch_linearizability",
        "experiments.test_multikey_linearizability",
        "experiments.test_same_key_contention",
        "experiments.test_concurrent_read_write",
    ],
    "recovery": [
        "experiments.test_checkpoint_recovery",
        "experiments.test_compaction",
        "experiments.test_crash_recovery",
        "experiments.test_truncated_log",
        "experiments.test_checksum_corruption",
        "experiments.test_inflight_batch_crash",
        "experiments.test_post_commit_batch_crash",
    ],
    "performance": [
        "experiments.test_benchmark",
    ],
}


def terminate_process_tree(process):
    """Terminate the experiment process and its child processes."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        process.communicate()


def run_experiment(module, timeout):
    """Execute one experiment in an isolated subprocess."""
    print(f"\n{'=' * 65}")
    print("EXPERIMENT:", module)
    print("=" * 65)

    started = time.perf_counter()
    status = "FAIL"
    exit_code = None
    stdout = ""
    stderr = ""

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            status = "PASS" if exit_code == 0 else "FAIL"

        except subprocess.TimeoutExpired:
            terminate_process_tree(process)
            stdout, stderr = process.communicate()
            exit_code = process.returncode
            status = "TIMEOUT"

            stderr += f"\nExperiment exceeded timeout of {timeout} seconds."

    except Exception as error:
        stderr = repr(error)

    duration = round(time.perf_counter() - started, 3)

    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")

    if stderr:
        print("\n--- STDERR ---")
        print(stderr)

    print(f"\nResult: {status} | Exit code: {exit_code}")
    print(f"Duration: {duration} seconds")

    return {
        "experiment": module,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "stdout": stdout,
        "stderr": stderr,
    }


def main():
    parser = argparse.ArgumentParser(
        description="KILL-IT database reliability campaign runner"
    )

    parser.add_argument(
        "--suite",
        choices=["all", *EXPERIMENTS.keys()],
        default="all",
        help="Experiment suite to execute",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Maximum seconds allowed per experiment",
    )

    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    if args.suite == "all":
        selected_experiments = [
            module
            for modules in EXPERIMENTS.values()
            for module in modules
        ]
        selected_suites = list(EXPERIMENTS.keys())
    else:
        selected_experiments = EXPERIMENTS[args.suite]
        selected_suites = [args.suite]

    if not selected_experiments:
        raise SystemExit("Selected suite contains no experiments.")

    print("\n========== KILL-IT TEST CAMPAIGN ==========")
    print("Selected suites:", ", ".join(selected_suites))
    print("Experiments:", len(selected_experiments))
    print("Timeout per experiment:", args.timeout, "seconds")

    campaign_started = time.perf_counter()
    results = []

    for module in selected_experiments:
        result = run_experiment(module, args.timeout)
        results.append(result)

    total_duration = round(
        time.perf_counter() - campaign_started, 3
    )

    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    timed_out = sum(r["status"] == "TIMEOUT" for r in results)

    overall_status = (
        "PASSED" if passed == len(results) else "FAILED"
    )

    timestamp = datetime.now(timezone.utc)
    timestamp_text = timestamp.strftime("%Y%m%dT%H%M%S%fZ")

    report = {
        "campaign": "KILL-IT",
        "timestamp_utc": timestamp.isoformat(),
        "status": overall_status,
        "suites": selected_suites,
        "timeout_seconds": args.timeout,
        "total_duration_seconds": total_duration,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "timed_out": timed_out,
        },
        "experiments": results,
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    report_path = LOG_DIR / f"suite-{timestamp_text}.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\n========== CAMPAIGN SUMMARY ==========")
    print("Status:", overall_status)
    print("Total:", len(results))
    print("Passed:", passed)
    print("Failed:", failed)
    print("Timed out:", timed_out)
    print("Duration:", total_duration, "seconds")
    print("Report:", report_path)

    if overall_status != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
