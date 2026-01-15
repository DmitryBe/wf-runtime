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

    output = await executor.ainvoke(wf_spec, {"x": 50})
    assert output is not None


# async def test_agent_builder_workflow():
#     schema_path = os.path.join("resources", "dsl_schema.yaml")
#     with open(schema_path, "r") as f:
#         schema = yaml.safe_load(f)

#     prompt_path = os.path.join("resources", "wf_builder_prompt.md")
#     with open(prompt_path, "r") as f:
#         prompt = f.read()

#     system_prompt = prompt.replace("{{schema}}", yaml.dump(schema))

#     import json

#     from langchain_core.messages import HumanMessage, SystemMessage
#     from langchain_core.prompts import ChatPromptTemplate
#     from langchain_openai import ChatOpenAI

#     from wf_runtime.dsl.models import Workflow

#     llm = ChatOpenAI(model="gpt-4.1")
#     prompt = ChatPromptTemplate(
#         [
#             SystemMessage(content=system_prompt),
#             HumanMessage(
#                 content="create a workflow that takes a number x. then it has 2 python nodes that run in parallel that multiple number by 2 and by 3. finnally we should have a python node that accept the output of the previous nodes and add them together. the workflow output must be val. The output must be a valid workflow definition in json only."
#             ),
#         ]
#     )
#     chain = prompt | llm

#     workflow = chain.invoke({})
#     print(workflow.content)

#     if isinstance(workflow.content, str):
#         json_str = workflow.content.strip()
#         if json_str.startswith("```"):
#             # Handle occasional fenced blocks like ```json ... ```
#             json_str = json_str.split("\n", 1)[1] if "\n" in json_str else ""
#             json_str = (
#                 json_str.rsplit("```", 1)[0]
#                 if json_str.rstrip().endswith("```")
#                 else json_str
#             ).strip()
#         try:
#             wf_obj = json.loads(json_str)
#         except json.JSONDecodeError as e:
#             raise AssertionError(
#                 f"LLM did not return valid JSON. Raw content:\n{workflow.content}"
#             ) from e
#     else:
#         wf_obj = workflow.content

#     out_path = os.path.join("examples", "workflows", "generated-wf.yaml")
#     with open(out_path, "w") as f:
#         yaml.safe_dump(wf_obj, f, sort_keys=False)


async def test_calc():
    import statistics

    spendings_2025 = [
        1_364,
        1_600,
        1_000,
        1_000,
        1_429,
        1_319,
        1_438,
        1_878,
        1_940,
        2_715,
        3_613,
        4_412,
    ]
    avg = statistics.mean(spendings_2025)
    std = statistics.stdev(spendings_2025)
    minimum = min(spendings_2025)
    maximum = max(spendings_2025)
    median = statistics.median(spendings_2025)
    q1 = statistics.quantiles(spendings_2025, n=4)[0]
    q3 = statistics.quantiles(spendings_2025, n=4)[2]
    total = sum(spendings_2025)
    count = len(spendings_2025)
    print(f"Spendings (US $ per month, 2025): {spendings_2025}")
    print(f"Count: {count}")
    print(f"Total: {total}")
    print(f"Average: {avg:.2f}")
    print(f"Median: {median:.2f}")
    print(f"Standard deviation: {std:.2f}")
    print(f"Minimum: {minimum}")
    print(f"Q1 (25th percentile): {q1:.2f}")
    print(f"Q3 (75th percentile): {q3:.2f}")
    print(f"Maximum: {maximum}")


async def test_http_request_node():
    url = "https://media.hswstatic.com/eyJidWNrZXQiOiJjb250ZW50Lmhzd3N0YXRpYy5jb20iLCJrZXkiOiJnaWZcL3NodXR0ZXJzdG9jay0yMjc4Nzc2MTg3LWhlcm8uanBnIiwiZWRpdHMiOnsicmVzaXplIjp7IndpZHRoIjo4Mjh9fX0="
    import base64

    import aiohttp

    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            assert resp.status == 200, f"Failed to get image: {resp.status}"
            img_bytes = await resp.read()
            # JPEG starts with 0xFF 0xD8 0xFF (next byte varies: APP0=0xE0, APP1=0xE1, etc.)
            # assert img_bytes.startswith(b"\xff\xd8\xff") or img_bytes.startswith(
            #     b"\x89PNG"
            # ), "Response is not an image"

            # encode
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            print(img_b64)

            # decode
            decoded_bytes = base64.b64decode(img_b64)
            assert decoded_bytes == img_bytes
