import os
import sys
import unittest

# Allow running tests without installing the package (src/ layout).
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from wf_runtime.backend.jq import JQRunnerImpl  # noqa: E402


class TestJQRunner(unittest.TestCase):
    def setUp(self):
        self.runner = JQRunnerImpl()

    def test_select_field(self):
        """Test selecting a single field from an object."""
        input_data = {"name": "Alice", "age": 30}
        result = self.runner.run(program=".name", input_data=input_data)
        self.assertEqual(result, "Alice")

    def test_select_nested_field(self):
        """Test selecting a nested field."""
        input_data = {"user": {"name": "Bob", "details": {"age": 25}}}
        result = self.runner.run(program=".user.details.age", input_data=input_data)
        self.assertEqual(result, 25)

    def test_filter_array(self):
        """Test filtering an array."""
        input_data = {"items": [1, 2, 3, 4, 5]}
        result = self.runner.run(
            program=".items[] | select(. > 3)", input_data=input_data
        )
        self.assertEqual(result, 4)  # .first() returns first match

    def test_map_array(self):
        """Test mapping over an array."""
        input_data = {"numbers": [1, 2, 3]}
        result = self.runner.run(program=".numbers[] | . * 2", input_data=input_data)
        self.assertEqual(result, 2)  # .first() returns first result

    def test_object_construction(self):
        """Test constructing a new object."""
        input_data = {"name": "Charlie", "age": 35}
        result = self.runner.run(
            program="{name: .name, double_age: (.age * 2)}", input_data=input_data
        )
        self.assertEqual(result, {"name": "Charlie", "double_age": 70})

    def test_array_operations(self):
        """Test array operations like length and indexing."""
        input_data = {"items": [10, 20, 30]}
        result = self.runner.run(program=".items | length", input_data=input_data)
        self.assertEqual(result, 3)

    def test_string_operations(self):
        """Test string operations."""
        input_data = {"message": "hello world"}
        result = self.runner.run(
            program=".message | ascii_upcase", input_data=input_data
        )
        self.assertEqual(result, "HELLO WORLD")

    def test_empty_input(self):
        """Test handling empty input."""
        input_data = {}
        result = self.runner.run(program=".test", input_data=input_data)
        self.assertIsNone(result)

    def test_complex_nested_structure(self):
        """Test with complex nested structure."""
        input_data = {
            "users": [
                {"name": "Alice", "scores": [85, 90, 88]},
                {"name": "Bob", "scores": [92, 87, 91]},
            ]
        }
        result = self.runner.run(program=".users[0].scores[0]", input_data=input_data)
        self.assertEqual(result, 85)

    def test_conditional_logic(self):
        """Test conditional logic in JQ."""
        input_data = {"value": 15}
        result = self.runner.run(
            program='if .value > 10 then "high" else "low" end', input_data=input_data
        )
        self.assertEqual(result, "high")

    def test_invalid_jq_program_raises_exception(self):
        """Test that invalid JQ syntax raises an exception."""
        input_data = {"test": "value"}
        with self.assertRaises(Exception) as context:
            self.runner.run(program="invalid jq syntax {", input_data=input_data)
        # jq library raises ValueError or similar for syntax errors
        self.assertIsInstance(context.exception, (ValueError, SyntaxError))

    def test_type_error_on_incompatible_operation(self):
        """Test that type errors are raised for incompatible operations."""
        input_data = {"value": "not_a_number"}
        # Trying to do arithmetic on a string should raise an error
        with self.assertRaises(Exception):
            self.runner.run(program=".value + 10", input_data=input_data)

    def test_index_out_of_bounds(self):
        """Test handling of out-of-bounds array access."""
        input_data = {"items": [1, 2, 3]}
        # Accessing index that doesn't exist returns None
        result = self.runner.run(program=".items[10]", input_data=input_data)
        self.assertIsNone(result)

    def test_division_by_zero(self):
        """Test that division by zero raises an error."""
        input_data = {"value": 10}
        with self.assertRaises(Exception):
            self.runner.run(program=".value / 0", input_data=input_data)


if __name__ == "__main__":
    unittest.main()
