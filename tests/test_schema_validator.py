import pytest

from wf_runtime.schema.validator import (
    InvalidSchemaError,
    validate_instance_safe,
    validate_schema_definition,
)


class TestValidateSchemaDefinition:
    def test_returns_schema_for_valid_schema(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
            "additionalProperties": False,
        }

        normalized = validate_schema_definition(schema)

        # Function currently returns the same dict (no copy/normalization step).
        assert normalized is schema
        assert normalized == schema

    def test_raises_invalid_schema_error_for_invalid_schema(self):
        # `type` must be a string or a list of strings, not an int.
        schema = {"type": 1}

        with pytest.raises(InvalidSchemaError) as excinfo:
            validate_schema_definition(schema)

        assert str(excinfo.value).startswith("Invalid JSON Schema:")


class TestValidateInstanceSafe:
    def test_returns_ok_true_for_valid_instance(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
            "additionalProperties": False,
        }

        res = validate_instance_safe({"x": 123}, schema)

        assert res.ok is True
        assert res.error is None

    def test_returns_ok_false_for_invalid_instance(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
            "additionalProperties": False,
        }

        res = validate_instance_safe({"x": "nope"}, schema)

        assert res.ok is False
        assert res.error is not None
        assert res.error.startswith("Schema validation failed:")
        assert "integer" in res.error

    def test_returns_ok_false_for_invalid_schema(self):
        res = validate_instance_safe({"x": 123}, {"type": 1})

        assert res.ok is False
        assert res.error is not None
        assert res.error.startswith("Invalid JSON Schema:")
