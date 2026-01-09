from __future__ import annotations

from dataclasses import dataclass

from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


@dataclass(frozen=True)
class StartNodeDef:
    """
    Internal system node definition for the workflow entrypoint.
    """

    id: str = "start"
    kind: str = "start"


def make_start_executor(
    node_def: StartNodeDef, compile_ctx: CompileContext
) -> NodeExecutor:
    """
    Start node is a no-op passthrough.
    """

    async def _exec(state: WorkflowState, runtime_ctx: RuntimeContext) -> WorkflowState:
        return state

    return _exec
