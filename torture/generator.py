import random


class WorkloadGenerator:

    def __init__(self, seed=42, keyspace=20):
        self.random = random.Random(seed)
        self.keyspace = keyspace
        self.history = []

    def generate_operation(self):

        operation_type = self.random.choice(
            ["PUT", "GET", "DELETE"]
        )

        key = f"key-{self.random.randint(1, self.keyspace)}"

        if operation_type == "PUT":
            value = f"value-{self.random.randint(1, 10000)}"

            operation = {
                "type": "PUT",
                "key": key,
                "value": value
            }

        elif operation_type == "GET":

            operation = {
                "type": "GET",
                "key": key
            }

        else:

            operation = {
                "type": "DELETE",
                "key": key
            }

        self.history.append(operation)

        return operation

    def generate(self, count):

        return [
            self.generate_operation()
            for _ in range(count)
        ]