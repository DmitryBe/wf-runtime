from __future__ import annotations

from functools import lru_cache

from wf_runtime.backend.jq import JQRunnerImpl
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.engine.nodes.base import CompileContext


@lru_cache(maxsize=1)
def get_compile_context() -> CompileContext:
    return CompileContext(jq=JQRunnerImpl(), sandbox=SandboxRunnerImpl())


@lru_cache(maxsize=1)
def get_workflow_executor() -> WorkflowExecutor:
    return WorkflowExecutor(compile_ctx=get_compile_context())
