import os

import yaml

from wf_runtime.backend.jq import JQRunnerImpl
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.engine.nodes.base import CompileContext


async def test_sandbox_code():

    yaml_path = os.path.join("examples", "workflows", "generated-wf.yaml")
    with open(yaml_path, "r") as f:
        wf_spec = yaml.safe_load(f)

    compile_ctx = CompileContext(jq=JQRunnerImpl(), sandbox=SandboxRunnerImpl())
    executor = WorkflowExecutor(compile_ctx=compile_ctx)
    await executor.validate_workflow(wf_spec)

    output = await executor.ainvoke(wf_spec, {"name": "John Doe", "order_amount": 50})
    assert output is not None


async def test_agent_builder_workflow():
    schema_path = os.path.join("resources", "dsl_schema.yaml")
    with open(schema_path, "r") as f:
        schema = yaml.safe_load(f)

    prompt_path = os.path.join("resources", "wf_builder_prompt.md")
    with open(prompt_path, "r") as f:
        prompt = f.read()

    system_prompt = prompt.replace("{{schema}}", yaml.dump(schema))

    import json

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    from wf_runtime.dsl.models import Workflow

    llm = ChatOpenAI(model="gpt-4.1")
    prompt = ChatPromptTemplate(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content="create a workflow that takes a number x. then it has 2 python nodes that run in parallel that multiple number by 2 and by 3. finnally we should have a python node that accept the output of the previous nodes and add them together. the workflow output must be val. The output must be a valid workflow definition in json only."
            ),
        ]
    )
    chain = prompt | llm

    workflow = chain.invoke({})
    print(workflow.content)

    if isinstance(workflow.content, str):
        json_str = workflow.content.strip()
        if json_str.startswith("```"):
            # Handle occasional fenced blocks like ```json ... ```
            json_str = json_str.split("\n", 1)[1] if "\n" in json_str else ""
            json_str = (
                json_str.rsplit("```", 1)[0]
                if json_str.rstrip().endswith("```")
                else json_str
            ).strip()
        try:
            wf_obj = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"LLM did not return valid JSON. Raw content:\n{workflow.content}"
            ) from e
    else:
        wf_obj = workflow.content

    out_path = os.path.join("examples", "workflows", "generated-wf.yaml")
    with open(out_path, "w") as f:
        yaml.safe_dump(wf_obj, f, sort_keys=False)
