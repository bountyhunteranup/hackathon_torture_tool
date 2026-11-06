import json
from collections import Counter
from pathlib import Path


class CampaignReport:

    def __init__(self, history_path):
        self.history_path = Path(history_path)
        self.records = []

    def load(self):
        with self.history_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON at line {line_number}: {error}"
                    ) from error

                self.records.append(record)

        return self

    def summarize(self):
        outcomes = Counter(
            record["outcome"] for record in self.records
        )

        operation_types = Counter(
            record["type"] for record in self.records
        )

        unknown_operations = [
            record
            for record in self.records
            if record["outcome"] == "UNKNOWN"
        ]

        return {
            "total": len(self.records),
            "outcomes": dict(outcomes),
            "operation_types": dict(operation_types),
            "unknown_operations": unknown_operations
        }

    def display(self):
        summary = self.summarize()

        print("\n========== CAMPAIGN REPORT ==========")

        print("Total operations:", summary["total"])

        print("\n--- OUTCOMES ---")
        for outcome, count in sorted(summary["outcomes"].items()):
            print(f"{outcome}: {count}")

        print("\n--- OPERATION TYPES ---")
        for operation, count in sorted(summary["operation_types"].items()):
            print(f"{operation}: {count}")

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