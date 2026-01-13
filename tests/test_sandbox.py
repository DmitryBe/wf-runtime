import os

import yaml

from wf_runtime.backend.jq import JQRunnerImpl
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.engine.nodes.base import CompileContext


async def test_sandbox_code():

    yaml_path = os.path.join("examples", "workflows", "add_numbers.yaml")
    with open(yaml_path, "r") as f:
        wf_spec = yaml.safe_load(f)

    compile_ctx = CompileContext(jq=JQRunnerImpl(), sandbox=SandboxRunnerImpl())
    executor = WorkflowExecutor(compile_ctx=compile_ctx)

    output = await executor.ainvoke(wf_spec, {"x": 3, "y": 4})
    assert output["res"] == 12
