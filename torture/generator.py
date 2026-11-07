import random


class WorkloadGenerator:

    def __init__(self, seed=42, keyspace=20):
        if not isinstance(keyspace, int) or isinstance(keyspace, bool) or keyspace < 1:
            raise ValueError("keyspace must be a positive integer")
        self.random = random.Random(seed)
        self.keyspace = keyspace
        self.history = []

    def generate_operation(self):

        operation_type = self.random.choices(
            ["PUT", "GET", "DELETE", "BATCH"],
            weights=[35, 30, 25, 10],
            k=1
        )[0]

        if operation_type == "BATCH":
            operations = []
            for _ in range(self.random.randint(1, 4)):
                batch_type = self.random.choice(["PUT", "DELETE"])
                item = {
                    "type": batch_type,
                    "key": f"key-{self.random.randint(1, self.keyspace)}"
                }
                if batch_type == "PUT":
                    item["value"] = f"value-{self.random.randint(1, 10000)}"
                operations.append(item)
            operation = {"type": "BATCH", "operations": operations}
            self.history.append(operation)
            return operation

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

        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("count must be a non-negative integer")

        return [
            self.generate_operation()
            for _ in range(count)
        ]
