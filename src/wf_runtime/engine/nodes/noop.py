from __future__ import annotations

from typing import Any, Dict

from wf_runtime.dsl.models import NoopNode
from wf_runtime.engine.mappings import (
    apply_output_mapping,
    resolve_inputs,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


def make_noop_executor(node_def: NoopNode, compile_ctx: CompileContext) -> NodeExecutor:
    """
    Noop node copies inputs to outputs.
    """
    node_id = node_def.id

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        inputs: Dict[str, Any] = resolve_inputs(state, node_def.input_mapping)
        outputs = apply_output_mapping(inputs, node_def.output_mapping)
        if compile_ctx.emit_event:
            await compile_ctx.emit_event(
                {
                    "type": "node_completed",
                    "node_id": node_id,
                    "kind": "noop",
                }
            )
        return write_node_outputs(state, node_id, outputs)

    return _exec
