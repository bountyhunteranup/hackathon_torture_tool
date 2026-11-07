
class Oracle:

    def __init__(self):
        self.expected_state = {}
        self.known_keys = set()

    def put(self, key, value):
        self.expected_state[key] = value
        self.known_keys.add(key)

    def get(self, key):
        return self.expected_state.get(key)

    def delete(self, key):
        self.expected_state.pop(key, None)
        self.known_keys.add(key)

    def apply_batch(self, operations):

        if not isinstance(operations, (list, tuple)) or not operations:
            raise ValueError("Batch must contain at least one operation")

        # Work on copies so the original state remains untouched
        # unless every operation is valid.
        next_state = self.expected_state.copy()
        next_known_keys = self.known_keys.copy()

        for operation in operations:

            operation_type = operation["type"]
            key = operation["key"]

            if not isinstance(key, str):
                raise ValueError("Batch keys must be strings")

            if operation_type == "PUT":

                if not isinstance(operation.get("value"), str):
                    raise ValueError("PUT values must be strings")

                next_state[key] = operation["value"]
                next_known_keys.add(key)

            elif operation_type == "DELETE":

                next_state.pop(key, None)
                next_known_keys.add(key)

            else:
                raise ValueError(
                    f"Unsupported batch operation: {operation_type}"
                )

        # Commit the new expected state only after processing
        # every operation successfully.
        self.expected_state = next_state
        self.known_keys = next_known_keys
