from torture.oracle import Oracle

oracle = Oracle()

oracle.put("apple", "100")
oracle.put("banana", "200")
oracle.put("apple", "500")

print(oracle.get("apple"))
print(oracle.get("banana"))

oracle.delete("apple")

print(oracle.get("apple"))
print(oracle.get("orange"))
print(oracle.expected_state)