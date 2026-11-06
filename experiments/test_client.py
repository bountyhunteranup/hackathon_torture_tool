from torture.client import DatabaseClient

db = DatabaseClient()

print("--- PUT ---")
status = db.put("balance", "500")
print("HTTP status:", status)

print("\n--- GET ---")
value = db.get("balance")
print("Retrieved value:", value)

print("\n--- DELETE ---")
status = db.delete("balance")
print("HTTP status:", status)

print("\n--- VERIFY DELETE ---")
value = db.get("balance")
print("Retrieved value:", value)

assert value is None

print("\nCLIENT TEST PASSED!")