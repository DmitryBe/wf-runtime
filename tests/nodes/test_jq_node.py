import pytest

import wf_runtime.engine.nodes.jq_transform as jq_node
from wf_runtime.dsl.models import JQNode
from wf_runtime.engine.nodes.base import CompileContext, RuntimeContext


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
