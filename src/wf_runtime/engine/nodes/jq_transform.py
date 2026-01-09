from __future__ import annotations

from typing import Any, Dict

from wf_runtime.dsl.models import JQNode
from wf_runtime.engine.mappings import (
    ResolveOptions,
    apply_output_mapping,
    resolve_inputs,
    write_error,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


def make_jq_executor(node_def: JQNode, compile_ctx: CompileContext) -> NodeExecutor:
    node_id = node_def.id

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        if compile_ctx.jq is None:
            return write_error(
                state, node_id, "missing_dependency", "JQ runner is not configured"
            )

        try:
            # JQ is often used to "pick" from optional branch outputs. Use
            # non-strict resolving so missing inputs become null/None.
            input_data: Dict[str, Any] = resolve_inputs(
                state, node_def.input_mapping, options=ResolveOptions(strict=False)
            )
            result = compile_ctx.jq.run(program=node_def.code, input_data=input_data)
            outputs = apply_output_mapping(result, node_def.output_mapping)
            if compile_ctx.emit_event:
                await compile_ctx.emit_event(
                    {
                        "type": "node_completed",
                        "node_id": node_id,
                        "kind": "jq_transform",
                    }
                )
            return write_node_outputs(state, node_id, outputs)
        except Exception as e:
            return write_error(state, node_id, "jq_error", str(e))

    return _exec
