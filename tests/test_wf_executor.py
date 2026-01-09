import os
import sys

import pytest

from wf_runtime.backend.jq import JQRunnerImpl
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.engine.nodes.base import CompileContext
from wf_runtime.schema.validator import SchemaValidationError


@pytest.fixture
def compile_ctx():
    """Fixture providing a CompileContext for tests."""
    return CompileContext(jq=JQRunnerImpl(), sandbox=SandboxRunnerImpl())


class TestWorkflowExecutor:

    async def test_run_simples(self, compile_ctx):

        wf_spec = _create_wf_spec(
            input_schema={"type": "object"}, output_schema={"type": "object"}
        )

        executor = WorkflowExecutor(compile_ctx=compile_ctx)
        result = await executor.ainvoke(wf_spec, {"x": 123})
        assert result == {"x": 123}

    async def test_run_with_invalid_input(self, compile_ctx):

        wf_spec = _create_wf_spec(
            input_schema={
                "type": "object",
                "properties": {"y": {"type": "integer"}},
                "required": ["y"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        )

        executor = WorkflowExecutor(compile_ctx=compile_ctx)
        with pytest.raises(SchemaValidationError) as excinfo:
            await executor.ainvoke(wf_spec, {"x": 123})

        msg = str(excinfo.value)
        assert "Workflow 'wf_1' input schema validation failed:" in msg
        assert "'y' is a required property" in msg

    async def test_run_with_invalid_output(self, compile_ctx):

        wf_spec = _create_wf_spec(
            input_schema={
                "type": "object",
            },
            output_schema={
                "type": "object",
                "properties": {"y": {"type": "integer"}},
                "required": ["y"],
                "additionalProperties": False,
            },
        )

        executor = WorkflowExecutor(compile_ctx=compile_ctx)
        with pytest.raises(SchemaValidationError) as excinfo:
            await executor.ainvoke(wf_spec, {"x": 123})

        msg = str(excinfo.value)
        assert "Workflow 'wf_1' output schema validation failed:" in msg
        assert "'y' is a required property" in msg


def _create_wf_spec(*, input_schema: dict, output_schema: dict) -> dict:
    return {
        "id": "wf_1",
        "version": 1,
        "input": {"schema": input_schema},
        "output": {
            "schema": output_schema,
            "input_mapping": {"x": "$nodes.step_one.x"},
        },
        "nodes": [
            {
                "id": "step_one",
                "kind": "noop",
                "input_mapping": {"x": "$input.x"},
            }
        ],
        "edges": [
            {"from": "start", "to": "step_one"},
            {"from": "step_one", "to": "end"},
        ],
    }
