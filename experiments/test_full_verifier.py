from torture.oracle import Oracle
from torture.verifier import Verifier


class MockDatabase:

    def __init__(self, state):
        self.state = state

    def dump(self):
        return self.state


oracle = Oracle()

oracle.put("apple", "red")
oracle.put("banana", "yellow")
oracle.put("mango", "green")


print("\n========== TEST 1: CORRECT STATE ==========")

database = MockDatabase({
    "apple": "red",
    "banana": "yellow",
    "mango": "green"
})

verifier = Verifier(database, oracle)

assert verifier.verify_full_state()


print("\n========== TEST 2: UNEXPECTED KEY ==========")

database = MockDatabase({
    "apple": "red",
    "banana": "yellow",
    "mango": "green",
    "ghost": "unexpected"
})

verifier = Verifier(database, oracle)

assert not verifier.verify_full_state()


print("\n========== TEST 3: MISSING KEY ==========")

database = MockDatabase({
    "apple": "red",
    "banana": "yellow"
})

verifier = Verifier(database, oracle)

assert not verifier.verify_full_state()


print("\n========== TEST 4: INCORRECT VALUE ==========")

database = MockDatabase({
    "apple": "red",
    "banana": "blue",
    "mango": "green"
})

verifier = Verifier(database, oracle)

assert not verifier.verify_full_state()


print("\nALL FULL-STATE TESTS PASSED!")