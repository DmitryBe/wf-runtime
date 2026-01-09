from __future__ import annotations

from typing import Callable, Dict

from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor
from wf_runtime.engine.nodes.end import make_end_executor
from wf_runtime.engine.nodes.jq_transform import make_jq_executor
from wf_runtime.engine.nodes.llm import make_llm_executor
from wf_runtime.engine.nodes.noop import make_noop_executor
from wf_runtime.engine.nodes.python_code import make_python_code_executor
from wf_runtime.engine.nodes.router import make_router_executor
from wf_runtime.engine.nodes.start import make_start_executor

NODE_EXECUTOR_FACTORIES: Dict[str, Callable[[object, CompileContext], NodeExecutor]] = {
    "start": make_start_executor,
    "end": make_end_executor,
    "noop": make_noop_executor,
    "jq_transform": make_jq_executor,
    "python_code": make_python_code_executor,
    "llm": make_llm_executor,
    "router": make_router_executor,
}
