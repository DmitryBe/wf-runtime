import wf_runtime.engine.nodes.python_code as python_code_node
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.dsl.models import JQNode, PythonCodeNode
from wf_runtime.engine.nodes.base import CompileContext, RuntimeContext


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

    async def test_python_code_with_match_case(self):
        node_def = PythonCodeNode.model_validate(
            {
                "id": "calc",
                "kind": "python_code",
                "code": """
                    x = input["x"]
                    match x:
                        case 1:
                            return {"result": "one"}
                        case 2:
                            return {"result": "two"}
                        case _:
                            return {"result": "unknown"}
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
            {"input": {"x": 1}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )
        assert update["data"]["calc"]["raw"]["result"] == "one"
