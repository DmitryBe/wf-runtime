from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from wf_runtime.dsl.models import JsonSchema


class SchemaValidationError(ValueError):
    """Raised when JSON instance does not conform to schema."""


class InvalidSchemaError(ValueError):
    """Raised when the JSON schema itself is invalid."""


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: Optional[str] = None
    path: Optional[str] = None
    schema_path: Optional[str] = None


def validate_schema_definition(schema: JsonSchema) -> Dict[str, Any]:
    """
    Validate that `schema` is a valid JSON Schema.

    Returns the normalized schema dict.
    Raises InvalidSchemaError if invalid.
    """
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as e:
        raise InvalidSchemaError(f"Invalid JSON Schema: {e.message}") from e

    return schema


def validate_instance(
    instance: Any,
    schema: Union[JsonSchema, Dict[str, Any]],
    *,
    format_check: bool = True,
) -> None:
    """
    Validate a JSON instance against a schema.

    - schema may be:
        - shorthand: "string"
        - JSON Schema dict
        - already-normalized dict

    Raises SchemaValidationError for instance errors.
    Raises InvalidSchemaError if schema is invalid.
    """

    # Validate the schema definition itself first (defensive)
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as e:
        raise InvalidSchemaError(f"Invalid JSON Schema: {e.message}") from e

    try:
        if format_check:
            Draft7Validator(schema, format_checker=FormatChecker()).validate(instance)
        else:
            Draft7Validator(schema).validate(instance)

    except ValidationError as e:
        path = ".".join(str(p) for p in e.path) if e.path else ""
        schema_path = ".".join(str(p) for p in e.schema_path) if e.schema_path else ""
        msg = e.message
        raise SchemaValidationError(
            f"Schema validation failed: {msg}"
            + (f" (path: {path})" if path else "")
            + (f" (schema_path: {schema_path})" if schema_path else "")
        ) from e


def validate_instance_safe(
    instance: Any,
    schema: Union[JsonSchema, Dict[str, Any]],
    *,
    format_check: bool = True,
) -> ValidationResult:
    """
    Non-throwing variant. Returns ValidationResult.
    """
    try:
        validate_instance(instance, schema, format_check=format_check)
        return ValidationResult(ok=True)
    except (SchemaValidationError, InvalidSchemaError) as e:
        # try to extract path hints if it was a jsonschema.ValidationError wrapped
        # we embedded them in the string already, so keep it simple:
        return ValidationResult(ok=False, error=str(e))
