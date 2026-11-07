
def is_linearizable(history, initial_state=None, final_state=None):
    """
    Check whether a PUT/GET/DELETE history has a legal sequential
    ordering that respects real-time precedence.

    Operations:
      PUT:    requires key and value
      GET:    requires key and response (None means absent)
      DELETE: requires key

    initial_state and final_state are dictionaries.
    A scalar initial_state is also supported for legacy single-key tests.
    """

    count = len(history)
    default_key = "__default__"

    # Construct the initial database state first.
    if initial_state is None:
        state = {}
    elif isinstance(initial_state, dict):
        state = dict(initial_state)
    else:
        state = {default_key: initial_state}

    if final_state is not None and not isinstance(final_state, dict):
        raise ValueError("final_state must be a dictionary or None")

    # Empty history cannot change the database.
    if count == 0:
        return final_state is None or state == final_state

    # Validate the initial state.
    for key, value in state.items():
        if not isinstance(key, str):
            raise ValueError("Database keys must be strings")
        if value is None:
            raise ValueError("Initial values cannot be None")

    # Validate operations.
    
    # Validate operations.
    for operation in history:
        if not isinstance(operation, dict):
            raise ValueError("Every operation must be a dictionary")

        operation_type = operation.get("type")

        if operation_type not in {"PUT", "GET", "DELETE", "BATCH"}:
            raise ValueError(
                f"Unsupported operation type: {operation_type}"
            )

        # Every operation needs a valid time interval.
        if "start" not in operation or "end" not in operation:
            raise ValueError("Every operation needs start and end")

        if operation["start"] > operation["end"]:
            raise ValueError("Operation start cannot exceed end")

        # Validate BATCH operations.
        if operation_type == "BATCH":
            children = operation.get("operations")

            if not isinstance(children, list) or not children:
                raise ValueError(
                    "BATCH requires a non-empty operations list"
                )

            for child in children:
                if not isinstance(child, dict):
                    raise ValueError(
                        "Batch operations must be dictionaries"
                    )

                child_type = child.get("type")

                if child_type not in {"PUT", "DELETE"}:
                    raise ValueError(
                        f"Unsupported batch operation: {child_type}"
                    )

                if not isinstance(child.get("key"), str):
                    raise ValueError(
                        "Batch operations require string keys"
                    )

                if child_type == "PUT":
                    if "value" not in child or child["value"] is None:
                        raise ValueError(
                            "Batch PUT requires a non-None value"
                        )

            continue

        # Validate individual PUT / GET / DELETE operations.
        key = operation.get("key", default_key)

        if not isinstance(key, str):
            raise ValueError("Operation keys must be strings")

        if operation_type == "PUT":
            if "value" not in operation or operation["value"] is None:
                raise ValueError("PUT requires a non-None value")

        elif operation_type == "GET":
            if "response" not in operation:
                raise ValueError("GET requires a response")


    # Build real-time precedence constraints.
    predecessors = [0] * count

    for i, first in enumerate(history):
        for j, second in enumerate(history):
            if i != j and first["end"] <= second["start"]:
                predecessors[j] |= 1 << i

    full_mask = (1 << count) - 1
    failed_states = set()

    def freeze(database):
        return tuple(sorted(database.items()))

    
    def search(done, current_state):
        if done == full_mask:
            return (
                final_state is None
                or current_state == final_state
            )

        memo_key = (done, freeze(current_state))

        if memo_key in failed_states:
            return False

        for i, operation in enumerate(history):
            bit = 1 << i

            if done & bit:
                continue

            if predecessors[i] & ~done:
                continue

            operation_type = operation["type"]
            key = operation.get("key", default_key)

            next_state = dict(current_state)

            if operation_type == "PUT":
                next_state[key] = operation["value"]

            elif operation_type == "DELETE":
                next_state.pop(key, None)

            elif operation_type == "BATCH":
                for child in operation["operations"]:
                    child_key = child["key"]

                    if child["type"] == "PUT":
                        next_state[child_key] = child["value"]

                    elif child["type"] == "DELETE":
                        next_state.pop(child_key, None)

            elif operation_type == "GET":
                actual_value = next_state.get(key)

                if actual_value != operation["response"]:
                    continue

            if search(done | bit, next_state):
                return True

        failed_states.add(memo_key)
        return False

    return search(0, state)

