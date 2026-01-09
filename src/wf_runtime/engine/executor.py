from typing import Any, Dict

from wf_runtime.compiler.compiler import WorkflowCompiler
from wf_runtime.dsl.models import Workflow
from wf_runtime.engine.nodes.base import CompileContext
from wf_runtime.schema.validator import (
    InvalidSchemaError,
    SchemaValidationError,
    validate_instance,
)


class WorkflowExecutor:

    def __init__(self, compile_ctx: CompileContext) -> None:
        self.compile_ctx = compile_ctx

    async def ainvoke(
        self,
        workflow_spec: Dict[str, Any],
        input_data: Dict[str, Any],
        runtime_ctx: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Compile and execute a workflow.
        """

        wf = Workflow.model_validate(workflow_spec)
        try:
            validate_instance(input_data, wf.input.schema_)
        except (SchemaValidationError, InvalidSchemaError) as e:
            raise type(e)(
                f"Workflow '{wf.id}' input schema validation failed: {e}"
            ) from e

        app = WorkflowCompiler(compile_ctx=self.compile_ctx).compile(wf)

        final_state = await app.ainvoke(
            {"input": input_data}, config={"configurable": runtime_ctx}
        )

        result = final_state["output"]
        try:
            validate_instance(result, wf.output.schema_)
        except (SchemaValidationError, InvalidSchemaError) as e:
            raise type(e)(
                f"Workflow '{wf.id}' output schema validation failed: {e}"
            ) from e
        return result
