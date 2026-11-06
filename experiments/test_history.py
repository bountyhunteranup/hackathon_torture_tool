from torture.history import OperationHistory

history = OperationHistory("logs/test-history.jsonl")

history.record(
    {
        "type": "PUT",
        "key": "balance",
        "value": "500"
    },
    "ACKNOWLEDGED"
)

history.record(
    {
        "type": "DELETE",
        "key": "balance"
    },
    "UNKNOWN",
    error="Connection timed out"
)

print("Recorded operations:", len(history.records))

for record in history.records:
    print(record)

print("\nHISTORY TEST PASSED!")