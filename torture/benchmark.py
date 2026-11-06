import math
from collections import Counter


class BenchmarkAnalyzer:

    @staticmethod
    def percentile(values, percentile):
        if not values:
            return 0.0

        ordered = sorted(values)

        # Nearest-rank percentile
        index = math.ceil(percentile / 100 * len(ordered)) - 1

        return ordered[max(0, index)]

    def analyze(self, results, elapsed_seconds, workers):

        latencies = [
            result["latency_ms"]
            for result in results
        ]

        outcomes = Counter(
            result["outcome"]
            for result in results
        )

        successful = outcomes["ACKNOWLEDGED"] + outcomes["NOT_FOUND"]
        total = len(results)

        return {
            "workers": workers,
            "total_operations": total,
            "successful_operations": successful,
            "elapsed_seconds": elapsed_seconds,
            "throughput": (
                total / elapsed_seconds if elapsed_seconds else 0
            ),
            "error_rate_percent": (
                (total - successful) / total * 100 if total else 0
            ),
            "latency_ms": {
                "average": (
                    sum(latencies) / len(latencies) if latencies else 0
                ),
                "p50": self.percentile(latencies, 50),
                "p95": self.percentile(latencies, 95),
                "p99": self.percentile(latencies, 99),
                "max": max(latencies, default=0)
            },
            "outcomes": dict(outcomes)
        }

    @staticmethod
    def display(report):

        print("\n========== BENCHMARK REPORT ==========")

        print("Workers:", report["workers"])
        print("Operations:", report["total_operations"])
        print("Successful:", report["successful_operations"])
        print("Duration:", round(report["elapsed_seconds"], 4), "seconds")
        print("Throughput:", round(report["throughput"], 2), "ops/sec")
        print("Error rate:", round(report["error_rate_percent"], 2), "%")

        print("\n--- LATENCY ---")

        for metric, value in report["latency_ms"].items():
            print(f"{metric.upper()}: {value:.3f} ms")

        print("\n--- OUTCOMES ---")

        for outcome, count in sorted(report["outcomes"].items()):
            print(f"{outcome}: {count}")

        print("\n======================================")