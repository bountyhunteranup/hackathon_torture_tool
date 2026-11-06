from torture.report import CampaignReport

history_path = (
    "logs/campaign-0epk8imx.jsonl"
)

report = CampaignReport(history_path)

report.load()

summary = report.display()

assert summary["total"] == 118
assert len(summary["unknown_operations"]) == 1

print("\nREPORT TEST PASSED!")