class Verifier:

    def __init__(self, database, oracle):
        self.database = database
        self.oracle = oracle

    def verify(self):
        failures = []

        for key in self.oracle.known_keys:

            expected = self.oracle.get(key)
            actual = self.database.get(key)

            if expected != actual:
                failures.append({
                    "key": key,
                    "expected": expected,
                    "actual": actual
                })

        if failures:
            print("\nVERIFICATION FAILED!")

            for failure in failures:
                print(failure)

            return False

        print("\nVERIFICATION PASSED!")
        print("Checked keys:", len(self.oracle.known_keys))

        return True
    
    def verify_full_state(self):
        expected = self.oracle.expected_state
        actual = self.database.dump()

        if not isinstance(actual, dict):
            raise TypeError(
                "Database dump must return a dictionary"
            )

        missing_keys = {
            key: value
            for key, value in expected.items()
            if key not in actual
        }

        unexpected_keys = {
            key: value
            for key, value in actual.items()
            if key not in expected
        }

        incorrect_values = {
            key: {
                "expected": expected[key],
                "actual": actual[key]
            }
            for key in expected.keys() & actual.keys()
            if expected[key] != actual[key]
        }

        passed = not (
            missing_keys
            or unexpected_keys
            or incorrect_values
        )

        print("\n--- FULL STATE VERIFICATION ---")
        print("Expected keys:", len(expected))
        print("Actual keys:", len(actual))
        print("Missing keys:", len(missing_keys))
        print("Unexpected keys:", len(unexpected_keys))
        print("Incorrect values:", len(incorrect_values))

        if missing_keys:
            print("Missing:", missing_keys)

        if unexpected_keys:
            print("Unexpected:", unexpected_keys)

        if incorrect_values:
            print("Incorrect:", incorrect_values)

        print(
            "\nFULL STATE VERIFICATION PASSED!"
            if passed
            else "\nFULL STATE VERIFICATION FAILED!"
        )

        return passed