
import json
from collections import Counter
from pathlib import Path


class CampaignReport:

    def __init__(self, history_path):
        self.history_path = Path(history_path)
        self.records = []

    def load(self):
        self.records.clear()

        with self.history_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON at line {line_number}: {error}"
                    ) from error

                if not isinstance(record, dict):
                    raise ValueError(
                        f"History line {line_number} must contain a JSON object"
                    )
                if not isinstance(record.get("type"), str) or not isinstance(
                    record.get("outcome"), str
                ):
                    raise ValueError(
                        f"History line {line_number} is missing type or outcome"
                    )

                self.records.append(record)

        return self

    def summarize(self):

        outcomes = Counter(
            record["outcome"] for record in self.records
        )

        verifications = Counter(
            record.get("verification", "NOT_CHECKED")
            for record in self.records
        )

        operation_types = Counter(
            record["type"] for record in self.records
        )

        unknown_operations = [
            record for record in self.records
            if record["outcome"] == "UNKNOWN"
        ]

        failed_verifications = [
            record for record in self.records
            if record.get("verification") == "FAILED"
        ]

        durations = [
            record["duration_ms"]
            for record in self.records
            if isinstance(record.get("duration_ms"), (int, float))
        ]

        latency = {
            "count": len(durations),
            "average_ms": (
                sum(durations) / len(durations) if durations else None
            ),
            "minimum_ms": min(durations) if durations else None,
            "maximum_ms": max(durations) if durations else None
        }

        individual_operations = sum(
            len(record.get("operations") or [])
            if record.get("type") == "BATCH" else 1
            for record in self.records
        )

        return {
            "total": len(self.records),
            "individual_operations": individual_operations,
            "outcomes": dict(outcomes),
            "verifications": dict(verifications),
            "operation_types": dict(operation_types),
            "unknown_operations": unknown_operations,
            "failed_verifications": failed_verifications,
            "latency": latency
        }

    def display(self):

        summary = self.summarize()

        print("\n========== CAMPAIGN REPORT ==========")

        print("Total requests:", summary["total"])
        print("Individual operations:", summary["individual_operations"])

        print("\n--- OUTCOMES ---")
        for outcome, count in sorted(summary["outcomes"].items()):
            print(f"{outcome}: {count}")

        print("\n--- VERIFICATION ---")
        for status, count in sorted(summary["verifications"].items()):
            print(f"{status}: {count}")

        print("\n--- OPERATION TYPES ---")
        for operation, count in sorted(summary["operation_types"].items()):
            print(f"{operation}: {count}")

        print("\n--- LATENCY ---")
        latency = summary["latency"]

        if latency["count"]:
            print(f"Average: {latency['average_ms']:.3f} ms")
            print(f"Minimum: {latency['minimum_ms']:.3f} ms")
            print(f"Maximum: {latency['maximum_ms']:.3f} ms")
        else:
            print("No timing data available.")

        print("\n--- FAILED VERIFICATIONS ---")

        if not summary["failed_verifications"]:
            print("None")
        else:
            for operation in summary["failed_verifications"]:
                print(
                    f"ID: {operation['operation_id']} | "
                    f"Type: {operation['type']} | "
                    f"Key: {operation['key']} | "
                    f"Expected/actual error: {operation['error']}"
                )

        print("\n--- UNKNOWN OPERATIONS ---")

        if not summary["unknown_operations"]:
            print("None")
        else:
            for operation in summary["unknown_operations"]:
                print(
                    f"ID: {operation['operation_id']} | "
                    f"Type: {operation['type']} | "
                    f"Key: {operation['key']} | "
                    f"Error: {operation['error']}"
                )

        print("\n=====================================")

        return summary
