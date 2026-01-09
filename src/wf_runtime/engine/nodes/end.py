from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from wf_runtime.engine.mappings import resolve_inputs
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


@dataclass(frozen=True)
class EndNodeDef:
    """
    Internal system node definition for the workflow finish node.
    """

    input_mapping: Dict[str, Any]
    id: str = "end"
    kind: str = "end"


def make_end_executor(
    node_def: EndNodeDef, compile_ctx: CompileContext
) -> NodeExecutor:
    """
    End node computes the final workflow output based on workflow.output.input_mapping.
    """

    async def _exec(state: WorkflowState, runtime_ctx: RuntimeContext) -> WorkflowState:
        outputs = resolve_inputs(state, node_def.input_mapping)
        return {"output": outputs}

    return _exec
