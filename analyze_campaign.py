
import json
import sys

from pathlib import Path


def analyze_campaign(report_path):
    path = Path(report_path)

    with path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    summary = report["summary"]
    experiments = report["experiments"]

    print("\n========== KILL-IT ANALYSIS ==========")

    print("Campaign:", report["campaign"])
    print("Timestamp:", report["timestamp_utc"])
    print("Overall status:", report["status"])

    print("\n--- EXPERIMENT SUMMARY ---")
    print("Total:", summary["total"])
    print("Passed:", summary["passed"])
    print("Failed:", summary["failed"])
    print("Timed out:", summary["timed_out"])

    print("\n--- EXPERIMENT DURATIONS ---")

    for experiment in experiments:
        print(
            experiment["experiment"],
            "->",
            experiment["duration_seconds"],
            "seconds",
            "|",
            experiment["status"],
        )

    total_duration = sum(
        experiment["duration_seconds"]
        for experiment in experiments
    )

    print("\nTotal experiment execution time:",
          round(total_duration, 3), "seconds")

    slowest = max(
        experiments,
        key=lambda experiment: experiment["duration_seconds"],
    )

    print(
        "Slowest experiment:",
        slowest["experiment"],
        "(",
        slowest["duration_seconds"],
        "seconds)",
    )

    print("\n--- FAILED EXPERIMENTS ---")

    failures = [
        experiment
        for experiment in experiments
        if experiment["status"] != "PASS"
    ]

    if not failures:
        print("No failed experiments.")
    else:
        for failure in failures:
            print(failure["experiment"])
            print("Exit code:", failure["exit_code"])
            print("Error:", failure["stderr"])

    print("\n======================================")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python analyze_campaign.py <report.json>"
        )

    analyze_campaign(sys.argv[1])
