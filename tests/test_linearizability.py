
from torture.linearizability import is_linearizable
import unittest

from torture.linearizability import is_linearizable


class TestLinearizability(unittest.TestCase):
    
    
    def test_atomic_batch_put_delete(self):
        history = [
            {
                "type": "BATCH",
                "operations": [
                    {"type": "PUT", "key": "A", "value": "100"},
                    {"type": "DELETE", "key": "B"},
                    {"type": "PUT", "key": "C", "value": "300"},
                ],
                "start": 1,
                "end": 5,
            },
            {
                "type": "GET",
                "key": "A",
                "response": "100",
                "start": 6,
                "end": 7,
            },
        ]

        self.assertTrue(
            is_linearizable(
                history,
                initial_state={"B": "20"},
                final_state={"A": "100", "C": "300"},
            )
        )

    def test_batch_is_one_atomic_operation(self):
        history = [
            {
                "type": "BATCH",
                "operations": [
                    {"type": "PUT", "key": "A", "value": "100"},
                    {"type": "PUT", "key": "B", "value": "200"},
                ],
                "start": 1,
                "end": 10,
            },
            {
                "type": "GET",
                "key": "A",
                "response": "100",
                "start": 2,
                "end": 3,
            },
            {
                "type": "GET",
                "key": "B",
                "response": None,
                "start": 4,
                "end": 5,
            },
        ]

        # Both GETs overlap the batch, but no legal sequential
        # ordering can explain seeing A updated and B absent.
        self.assertFalse(
            is_linearizable(history, initial_state={})
        )

    def test_batch_rejects_invalid_child(self):
        history = [
            {
                "type": "BATCH",
                "operations": [
                    {"type": "GET", "key": "A"},
                ],
                "start": 1,
                "end": 2,
            }
        ]

        with self.assertRaises(ValueError):
            is_linearizable(history, {})

    
    def test_empty_history_requires_unchanged_final_state(self):
        initial = {"A": "100"}

        self.assertTrue(
            is_linearizable(
                [],
                initial_state=initial,
                final_state={"A": "100"},
            )
        )

        self.assertFalse(
            is_linearizable(
                [],
                initial_state=initial,
                final_state={"A": "200"},
            )   
        )
    
    
    def test_final_state_matches_legal_execution(self):
        history = [
            {
                "type": "PUT",
                "key": "A",
                "value": "100",
                "start": 1,
                "end": 4,
            },
            {
                "type": "PUT",
                "key": "A",
                "value": "200",
                "start": 2,
                "end": 3,
            },
        ]

        self.assertTrue(
            is_linearizable(
                history,
                initial_state={},
                final_state={"A": "100"},
            )
        )

    def test_final_state_rejects_impossible_result(self):
        history = [
            {
                "type": "PUT",
                "key": "A",
                "value": "100",
                "start": 1,
                "end": 4,
            },
            {
                "type": "PUT",
                "key": "A",
                "value": "200",
                "start": 2,
                "end": 3,
            },
        ]

        self.assertFalse(
            is_linearizable(
                history,
                initial_state={},
                final_state={"A": "300"},
            )
        )


    def test_empty_history(self):
        self.assertTrue(is_linearizable([], None))

    def test_single_put(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 2}
        ]

        self.assertTrue(is_linearizable(history, None))

    def test_put_then_get(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 2},
            {"type": "GET", "response": "A", "start": 3, "end": 4},
        ]

        self.assertTrue(is_linearizable(history, None))

    def test_stale_read_is_rejected(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 2},
            {"type": "PUT", "value": "B", "start": 3, "end": 4},
            {"type": "GET", "response": "A", "start": 5, "end": 6},
        ]

        self.assertFalse(is_linearizable(history, None))

    def test_overlapping_writes_can_be_reordered(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 4},
            {"type": "PUT", "value": "B", "start": 2, "end": 3},
            {"type": "GET", "response": "B", "start": 5, "end": 6},
        ]

        self.assertTrue(is_linearizable(history, None))

    def test_delete_then_get(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 2},
            {"type": "DELETE", "start": 3, "end": 4},
            {"type": "GET", "response": None, "start": 5, "end": 6},
        ]

        self.assertTrue(is_linearizable(history, None))

    def test_read_after_delete_cannot_return_old_value(self):
        history = [
            {"type": "PUT", "value": "A", "start": 1, "end": 2},
            {"type": "DELETE", "start": 3, "end": 4},
            {"type": "GET", "response": "A", "start": 5, "end": 6},
        ]

        self.assertFalse(is_linearizable(history, None))

    def test_invalid_operation_is_rejected(self):
        history = [
            {"type": "MAGIC", "start": 1, "end": 2}
        ]

        with self.assertRaises(ValueError):
            is_linearizable(history, None)

    def test_invalid_timestamp_order_is_rejected(self):
        history = [
            {"type": "PUT", "value": "A", "start": 5, "end": 2}
        ]

        with self.assertRaises(ValueError):
            is_linearizable(history, None)


    def test_put_and_get_multiple_keys(self):
        history = [
            {
                "type": "PUT", "key": "A", "value": "100",
                "start": 1, "end": 2
            },
            {
                "type": "PUT", "key": "B", "value": "200",
                "start": 3, "end": 4
            },
            {
                "type": "GET", "key": "A", "response": "100",
                "start": 5, "end": 6
            },
            {
                "type": "GET", "key": "B", "response": "200",
                "start": 7, "end": 8
            },
        ]

        self.assertTrue(is_linearizable(history, {}))

    def test_initial_state_with_multiple_keys(self):
        history = [
            {
                "type": "GET", "key": "A", "response": "100",
                "start": 1, "end": 2
            },
            {
                "type": "GET", "key": "B", "response": "200",
                "start": 3, "end": 4
            },
        ]

        initial = {"A": "100", "B": "200"}

        self.assertTrue(is_linearizable(history, initial))

    def test_delete_only_affects_its_own_key(self):
        history = [
            {
                "type": "PUT", "key": "A", "value": "100",
                "start": 1, "end": 2
            },
            {
                "type": "PUT", "key": "B", "value": "200",
                "start": 3, "end": 4
            },
            {
                "type": "DELETE", "key": "A",
                "start": 5, "end": 6
            },
            {
                "type": "GET", "key": "A", "response": None,
                "start": 7, "end": 8
            },
            {
                "type": "GET", "key": "B", "response": "200",
                "start": 9, "end": 10
            },
        ]

        self.assertTrue(is_linearizable(history, {}))

    def test_stale_value_on_another_key_is_rejected(self):
        history = [
            {
                "type": "PUT", "key": "A", "value": "100",
                "start": 1, "end": 2
            },
            {
                "type": "PUT", "key": "B", "value": "200",
                "start": 3, "end": 4
            },
            {
                "type": "GET", "key": "B", "response": "100",
                "start": 5, "end": 6
            },
        ]

        self.assertFalse(is_linearizable(history, {}))


if __name__ == "__main__":
    unittest.main()
