from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from wf_runtime.compiler import builder
from wf_runtime.dsl.models import BranchEdge, SimpleEdge, Workflow
from wf_runtime.engine.nodes.base import CompileContext
from wf_runtime.engine.nodes.end import EndNodeDef
from wf_runtime.engine.nodes.start import StartNodeDef
from wf_runtime.engine.state import WorkflowState


class WorkflowCompiler:
    """
    Compiles a Workflow DSL definition into a LangGraph application.
    """

    def __init__(self, compile_ctx: CompileContext | None = None):
        """
        Initialize the compiler with compile-time context.

        Args:
            compile_ctx: Compile-time dependencies reused across all graph executions.
                        If None, an empty CompileContext is created.
        """
        self.compile_ctx = compile_ctx or CompileContext()

    def compile(self, workflow: Workflow) -> CompiledStateGraph:
        """
        Compile the workflow into a LangGraph app.
        """
        self._validate(workflow)

        graph = StateGraph(WorkflowState)

        self._add_system_nodes(graph, workflow)

        for node in workflow.nodes:
            builder.add_node(graph, node, self.compile_ctx)

        self._add_edges(graph, workflow)

        graph.set_entry_point("start")
        graph.set_finish_point("end")

        return graph.compile(name=workflow.id)

    def _add_system_nodes(self, graph: StateGraph, workflow: Workflow) -> None:
        """
        Adds the start and end system nodes to the graph.
        """
        builder.add_system_node(
            graph,
            node_id="start",
            kind="start",
            node_def=StartNodeDef(),
            compile_ctx=self.compile_ctx,
        )
        builder.add_system_node(
            graph,
            node_id="end",
            kind="end",
            node_def=EndNodeDef(input_mapping=workflow.output.input_mapping),
            compile_ctx=self.compile_ctx,
        )

    def _validate(self, workflow: Workflow) -> None:
        """
        High-level semantic validation.
        (DSL-level structural checks should already be done by Pydantic.)
        """
        node_ids = {n.id for n in workflow.nodes}

        if "start" in node_ids:
            raise ValueError("'start' is reserved and cannot be a node id")
        if "end" in node_ids:
            raise ValueError("'end' is reserved and cannot be a node id")

        if not any(e.from_ == "start" for e in workflow.edges):
            raise ValueError("Workflow must have at least one edge from 'start'")

        def _reaches_end(edge) -> bool:
            if isinstance(edge, SimpleEdge):
                return edge.to == "end"
            # BranchEdge
            return any(r.to == "end" for r in edge.routes)

        if not any(_reaches_end(e) for e in workflow.edges):
            raise ValueError("Workflow must have at least one edge to 'end'")

    def _add_edges(self, graph: StateGraph, workflow: Workflow) -> None:
        """
        Adds edges, grouping conditional edges for routers.
        """
        # Flatten BranchEdge into per-route SimpleEdges so downstream builder helpers
        by_from: Dict[str, List[SimpleEdge]] = defaultdict(list)
        for e in workflow.edges:
            if isinstance(e, BranchEdge):
                for r in e.routes:
                    by_from[e.from_].append(
                        SimpleEdge(from_=e.from_, to=r.to, when_label=r.when_label)
                    )
            else:
                by_from[e.from_].append(e)

        for src, edges in by_from.items():
            conditional = [e for e in edges if e.when_label]
            normal = [e for e in edges if not e.when_label]

            for e in normal:
                builder.add_edge(graph, e)

            if conditional:
                builder.add_conditional_edges(
                    graph,
                    router_node_id=src,
                    edges=conditional,
                )
