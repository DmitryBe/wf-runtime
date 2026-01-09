import os

import pytest

import wf_runtime.engine.nodes.jq_transform as jq_node
import wf_runtime.engine.nodes.llm as llm_node
import wf_runtime.engine.nodes.python_code as python_code_node
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.dsl.models import JQNode, LLMNode, PythonCodeNode
from wf_runtime.engine.nodes.base import CompileContext, RuntimeContext


class TestLLMNode:
    async def test_llm_node_text_prompt(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY is not set")

        node_def = LLMNode.model_validate(
            {
                "id": "llm_extract",
                "kind": "llm",
                "model": "openai:gpt-4.1-mini",
                "prompt": "extract name from the message: {txt}",
                "output_schema": {
                    "type": "object",
                    "title": "info_extraction",
                    "description": "Extract information from the message.",
                    "properties": {"name": {"type": "string"}},
                },
                "input_mapping": {"txt": "$input.txt"},
                "output_mapping": {},
            }
        )

        executor = llm_node.make_llm_executor(node_def, CompileContext())
        update = await executor(
            {"input": {"txt": "Hello, my name is John Doe"}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )

        assert update == {
            "data": {"llm_extract": {"name": "John Doe"}},
            "last_node": "llm_extract",
        }

    async def test_llm_node_multimodal_prompt(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY is not set")

        node_def = LLMNode.model_validate(
            {
                "id": "llm_extract",
                "kind": "llm",
                "model": "openai:gpt-4.1-mini",
                "prompt": [
                    ("text", "Extract the number of cats from the provided image"),
                    ("image_url", "{image_url1}"),
                ],
                "output_schema": {
                    "type": "object",
                    "title": "info_extraction",
                    "description": "Extract information from the message.",
                    "properties": {"number_of_cats": {"type": "number"}},
                },
                "input_mapping": {"image_url1": "$input.image_url1"},
                "output_mapping": {},
            }
        )

        executor = llm_node.make_llm_executor(node_def, CompileContext())
        update = await executor(
            {
                "input": {
                    "image_url1": "https://i.natgeofe.com/n/548467d8-c5f1-4551-9f58-6817a8d2c45e/NationalGeographic_2572187_16x9.jpg?w=1200"
                },
                "data": {},
                "errors": [],
            },
            RuntimeContext(configurable={}),
        )

        assert update["data"]["llm_extract"]["number_of_cats"] == 1


class TestPythonCodeNode:
    async def test_python_code_node_happy_path(self):
        node_def = PythonCodeNode.model_validate(
            {
                "id": "calc",
                "kind": "python_code",
                "code": """
                    x = input["x"]
                    return {"doubled": x * 2, "meta": {"x": x}}
                """,
                "timeout_s": 1.0,
                "input_mapping": {"x": "$input.x"},
                "output_mapping": {
                    "doubled": "$.doubled",
                    "raw": "$result",
                },
            }
        )
        executor = python_code_node.make_python_code_executor(
            node_def, CompileContext(sandbox=SandboxRunnerImpl())
        )
        update = await executor(
            {"input": {"x": 21}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )
        assert update["last_node"] == "calc"
        assert update["data"]["calc"]["doubled"] == 42
        assert update["data"]["calc"]["raw"] == {"doubled": 42, "meta": {"x": 21}}


class TestJQTransformNode:
    async def test_jq_transform_node_happy_path(self):
        pytest.importorskip("jq")
        from wf_runtime.backend.jq import JQRunnerImpl

        node_def = JQNode.model_validate(
            {
                "id": "transform",
                "kind": "jq_transform",
                "code": "{x: .x, doubled: (.x * 2)}",
                "input_mapping": {"x": "$input.x"},
                "output_mapping": {
                    "doubled": "$.doubled",
                    "all": "$result",
                },
            }
        )

        executor = jq_node.make_jq_executor(node_def, CompileContext(jq=JQRunnerImpl()))
        update = await executor(
            {"input": {"x": 21}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )

        assert update["last_node"] == "transform"
        assert update["data"]["transform"]["doubled"] == 42
        assert update["data"]["transform"]["all"] == {"x": 21, "doubled": 42}
