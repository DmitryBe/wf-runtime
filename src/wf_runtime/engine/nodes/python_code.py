from __future__ import annotations

from typing import Any, Dict

from wf_runtime.dsl.models import PythonCodeNode
from wf_runtime.engine.mappings import (
    apply_output_mapping,
    resolve_inputs,
    write_error,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


def make_python_code_executor(
    node_def: PythonCodeNode, compile_ctx: CompileContext
) -> NodeExecutor:
    node_id = node_def.id

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        if compile_ctx.sandbox is None:
            return write_error(
                state, node_id, "missing_dependency", "Sandbox runner is not configured"
            )

        try:
            input_data: Dict[str, Any] = resolve_inputs(state, node_def.input_mapping)
            result = await compile_ctx.sandbox.run(
                code=node_def.code, input_data=input_data, timeout_s=node_def.timeout_s
            )
            outputs = apply_output_mapping(result, node_def.output_mapping)
            if compile_ctx.emit_event:
                await compile_ctx.emit_event(
                    {
                        "type": "node_completed",
                        "node_id": node_id,
                        "kind": "python_code",
                    }
                )
            return write_node_outputs(state, node_id, outputs)
        except Exception as e:
            return write_error(state, node_id, "python_code_error", str(e))

    return _exec
