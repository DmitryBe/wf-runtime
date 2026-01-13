from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from wf_runtime.dsl.models import Edge, Node
from wf_runtime.engine.nodes.base import CompileContext, RuntimeContext
from wf_runtime.engine.nodes_registry import NODE_EXECUTOR_FACTORIES
from wf_runtime.engine.state import WorkflowState


@dataclass(frozen=True)
class BuilderOptions:
    """
    Options for the builder.
    """

    # Whether to fast fail the workflow if any node fails
    fail_fast: bool = field(default=True)


def add_node(
    graph: StateGraph,
    node_def: Node,
    compile_ctx: CompileContext,
    options: BuilderOptions,
) -> None:
    """
    Add a DSL node to the LangGraph graph.

    The node executor is created here and closed over CompileContext.
    """
    if node_def.kind not in NODE_EXECUTOR_FACTORIES:
        raise ValueError(f"Unsupported node kind: {node_def.kind}")

    factory = NODE_EXECUTOR_FACTORIES[node_def.kind]
    executor = factory(node_def, compile_ctx)

    async def _langgraph_node(
        state: WorkflowState, config: RunnableConfig
    ) -> WorkflowState:
        ctx: RuntimeContext = RuntimeContext(
            configurable=config.get("configurable", {})
        )
        state_update = await executor(state, ctx)
        if (
            options.fail_fast
            and "errors" in state_update
            and len(state_update["errors"]) > 0
        ):
            errors = state_update["errors"]
            last_error = errors[-1]
            last_error_message = (
                last_error["message"]
                if isinstance(last_error, dict) and "message" in last_error
                else last_error
            )
            raise RuntimeError(
                f"Node {node_def.id} failed with error: {last_error_message}"
            )
        return state_update

    graph.add_node(node_def.id, _langgraph_node)


def add_system_node(
    graph: StateGraph,
    *,
    node_id: str,
    kind: str,
    node_def: object,
    compile_ctx: CompileContext,
) -> None:
    """
    Add an internal (non-DSL) node like 'start' / 'end'.
    """
    if kind not in NODE_EXECUTOR_FACTORIES:
        raise ValueError(f"Unsupported node kind: {kind}")

    factory = NODE_EXECUTOR_FACTORIES[kind]
    executor = factory(node_def, compile_ctx)

    async def _langgraph_node(
        state: WorkflowState, config: RunnableConfig
    ) -> WorkflowState:
        ctx: RuntimeContext = RuntimeContext(
            configurable=config.get("configurable", {})
        )
        return await executor(state, ctx)

    graph.add_node(node_id, _langgraph_node)


def add_edge(
    graph: StateGraph,
    edge: Edge,
) -> None:
    """
    Add a simple (non-conditional) edge.
    """
    src = edge.from_
    dst = edge.to
    graph.add_edge(src, dst)


def add_conditional_edges(
    graph: StateGraph,
    *,
    router_node_id: str,
    edges: List[Edge],
) -> None:
    """
    Add conditional edges for a router node.

    Router node must have written:
      state["data"][router_node_id]["label"]
    """

    def _router_fn(state: WorkflowState) -> str:
        data = state.get("data", {})
        node_out = data.get(router_node_id, {})
        return node_out.get("label", "else")

    mapping: Dict[str, str] = {}
    for e in edges:
        label = e.when_label
        if not label:
            continue
        # Route to the 'end' node (not LangGraph END) so we can compute outputs.
        mapping[label] = "end" if e.to == "end" else e.to

    # fallback
    mapping.setdefault("else", "end")

    graph.add_conditional_edges(router_node_id, _router_fn, mapping)
