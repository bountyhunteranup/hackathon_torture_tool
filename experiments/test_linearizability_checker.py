from torture.linearizability import is_linearizable


def main():
    # Case 1: Valid history.
    # PUT A and PUT B overlap, so either can be ordered first.
    # The GET happens after both and returns B.
    valid_history = [
        {"type": "PUT", "value": "A", "start": 10, "end": 40},
        {"type": "PUT", "value": "B", "start": 20, "end": 30},
        {"type": "GET", "response": "B", "start": 41, "end": 50},
    ]

    # Case 2: Impossible history.
    # A completes, then B completes, then GET returns the old value A.
    impossible_history = [
        {"type": "PUT", "value": "A", "start": 10, "end": 20},
        {"type": "PUT", "value": "B", "start": 30, "end": 40},
        {"type": "GET", "response": "A", "start": 50, "end": 60},
    ]

    valid_result = is_linearizable(valid_history, "initial")
    impossible_result = is_linearizable(impossible_history, "initial")

    print("Valid history accepted:", valid_result)
    print("Impossible history rejected:", not impossible_result)

    assert valid_result is True
    assert impossible_result is False

    print("\nCHECKER SELF-TEST PASSED!")


if __name__ == "__main__":
    main()
