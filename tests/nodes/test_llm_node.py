import os

import pytest

import wf_runtime.engine.nodes.llm as llm_node
from wf_runtime.dsl.models import LLMNode
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
