from torture.client import DatabaseClient
from torture.runner import TortureRunner
from torture.verifier import Verifier


database = DatabaseClient()
runner = TortureRunner(database)

print("--- INSERTING DATA ---")

runner.put("apple", "100")
runner.put("banana", "200")
runner.put("mango", "300")

print("Oracle:", runner.oracle.expected_state)

print("\n--- UPDATING DATA ---")

runner.put("banana", "900")

print("Oracle:", runner.oracle.expected_state)

print("\n--- READING DATA ---")

print("Apple:", runner.get("apple"))
print("Banana:", runner.get("banana"))

print("\n--- DELETING DATA ---")

runner.delete("apple")

print("Oracle:", runner.oracle.expected_state)

print("\n--- VERIFYING DELETION ---")

print("Apple:", runner.get("apple"))

print("\nOperations acknowledged:", runner.operations)

print("\nRUNNER TEST PASSED!")

print("\n--- FULL DATABASE VERIFICATION ---")

verifier = Verifier(database, runner.oracle)

assert verifier.verify()