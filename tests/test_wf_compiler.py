import pytest

from wf_runtime.backend.jq import JQRunnerImpl
from wf_runtime.backend.sandbox import SandboxRunnerImpl
from wf_runtime.compiler.compiler import WorkflowCompiler  # noqa: E402
from wf_runtime.dsl.models import Workflow  # noqa: E402
from wf_runtime.engine.nodes.base import CompileContext


@pytest.fixture
def compile_ctx():
    """Fixture providing a CompileContext for tests."""
    return CompileContext(jq=JQRunnerImpl(), sandbox=SandboxRunnerImpl())


class TestWorkflowCompiler:

    async def test_run_simple_workflow(self, compile_ctx):
        wf = Workflow.model_validate(
            {
                "id": "noop_compile_wf",
                "version": 1,
                "input": {
                    "schema": {
                        "type": "object",
                        "properties": {"x": {"type": "integer"}},
                        "required": ["x"],
                        "additionalProperties": False,
                    }
                },
                "output": {
                    "schema": {"type": "object"},
                    "input_mapping": {"x": "$input.x"},
                },
                "nodes": [],
                "edges": [{"from": "start", "to": "end"}],
            }
        )

        instance = WorkflowCompiler(compile_ctx=compile_ctx).compile(wf)
        final_state = await instance.ainvoke(
            {"input": {"x": 123}}, config={"configurable": {}}
        )
        assert final_state["output"] == {"x": 123}

    async def test_run_noop_workflow(self, compile_ctx):
        wf = Workflow.model_validate(
            {
                "id": "noop_compile_wf",
                "version": 1,
                "input": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "string"},
                        },
                        "required": ["x", "y"],
                        "additionalProperties": False,
                    }
                },
                "output": {
                    "schema": {"type": "object"},
                    "input_mapping": {"x": "$nodes.step_one.x"},
                },
                "nodes": [
                    {
                        "id": "step_one",
                        "kind": "noop",
                        "input_mapping": {"x": "$input.x"},
                        "output_mapping": {},  # map result to output
                    }
                ],
                "edges": [
                    {"from": "start", "to": "step_one"},
                    {"from": "step_one", "to": "end"},
                ],
            }
        )

        instance = WorkflowCompiler(compile_ctx=compile_ctx).compile(wf)
        final_state = await instance.ainvoke(
            {"input": {"x": 123, "y": "hello"}}, config={"configurable": {}}
        )

        assert final_state["last_node"] == "step_one"
        assert final_state["output"] == {"x": 123}

    async def test_run_wf_with_sequential_nodes(self, compile_ctx):
        wf = Workflow.model_validate(
            {
                "id": "sequential_nodes_wf",
                "version": 1,
                "input": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "num": {"type": "integer"},
                            "text": {"type": "string"},
                        },
                        "required": ["num", "text"],
                        "additionalProperties": False,
                    }
                },
                "output": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "result": {"type": "string"},
                        },
                        "required": ["result"],
                        "additionalProperties": False,
                    },
                    "input_mapping": {"result": "$nodes.step_concat"},
                },
                "nodes": [
                    {
                        "id": "step_transform",
                        "kind": "python_code",
                        "input_mapping": {"num": "$input.num", "text": "$input.text"},
                        "code": """
num2 = input["num"] * 2
text_upper = input["text"].upper()
return {"num2": num2, "text_upper": text_upper}
""",
                        "output_mapping": {
                            "num2": "$.num2",
                            "text_upper": "$.text_upper",
                        },
                    },
                    {
                        "id": "step_concat",
                        "kind": "jq_transform",
                        "input_mapping": {
                            "num2": "$nodes.step_transform.num2",
                            "text_upper": "$nodes.step_transform.text_upper",
                        },
                        # concat text - number, output should be in `result`
                        "code": '.text_upper + "-" + (.num2 | tostring)',
                        # leave output_mapping empty so node outputs {"result": <jq string>}
                        "output_mapping": {},
                    },
                ],
                "edges": [
                    {"from": "start", "to": "step_transform"},
                    {"from": "step_transform", "to": "step_concat"},
                    {"from": "step_concat", "to": "end"},
                ],
            }
        )

        instance = WorkflowCompiler(compile_ctx=compile_ctx).compile(wf)
        final_state = await instance.ainvoke(
            {"input": {"num": 7, "text": "hello"}}, config={"configurable": {}}
        )

        assert final_state["last_node"] == "step_concat"
        assert final_state["output"] == {"result": "HELLO-14"}

    async def test_run_wf_with_concurrent_execution(self, compile_ctx):
        wf = Workflow.model_validate(
            {
                "id": "concurrent_execution_wf",
                "version": 1,
                "input": {
                    "schema": {
                        "type": "object",
                        "properties": {"val": {"type": "integer"}},
                        "required": ["val"],
                        "additionalProperties": False,
                    }
                },
                "output": {
                    "schema": {
                        "type": "object",
                        "properties": {"result": {"type": "integer"}},
                        "required": ["result"],
                        "additionalProperties": False,
                    },
                    "input_mapping": {"result": "$nodes.sum_all.result"},
                },
                "nodes": [
                    {
                        "id": "mult_by_2",
                        "kind": "python_code",
                        "input_mapping": {"val": "$input.val"},
                        "code": """
return {"value": input["val"] * 2}
""",
                        "output_mapping": {"value": "$.value"},
                    },
                    {
                        "id": "mult_by_3",
                        "kind": "python_code",
                        "input_mapping": {"val": "$input.val"},
                        "code": """
return {"value": input["val"] * 3}
""",
                        "output_mapping": {"value": "$.value"},
                    },
                    {
                        "id": "mult_by_4",
                        "kind": "python_code",
                        "input_mapping": {"val": "$input.val"},
                        "code": """
return {"value": input["val"] * 4}
""",
                        "output_mapping": {"value": "$.value"},
                    },
                    {
                        "id": "sum_all",
                        "kind": "python_code",
                        "input_mapping": {
                            "a": "$nodes.mult_by_2.value",
                            "b": "$nodes.mult_by_3.value",
                            "c": "$nodes.mult_by_4.value",
                        },
                        "code": """
total = input["a"] + input["b"] + input["c"]
return {"result": total}
""",
                        "output_mapping": {"result": "$.result"},
                    },
                ],
                "edges": [
                    {"from": "start", "to": "mult_by_2"},
                    {"from": "start", "to": "mult_by_3"},
                    {"from": "start", "to": "mult_by_4"},
                    {"from": "mult_by_2", "to": "sum_all"},
                    {"from": "mult_by_3", "to": "sum_all"},
                    {"from": "mult_by_4", "to": "sum_all"},
                    {"from": "sum_all", "to": "end"},
                ],
            }
        )

        instance = WorkflowCompiler(compile_ctx=compile_ctx).compile(wf)
        final_state = await instance.ainvoke(
            {"input": {"val": 5}}, config={"configurable": {}}
        )

        assert final_state["output"] == {"result": 45}

    async def test_run_wf_with_router_branching(self, compile_ctx):
        wf = Workflow.model_validate(
            {
                "id": "router_branching_wf",
                "version": 1,
                "input": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "op": {"type": "string"},
                        },
                        "required": ["x", "y", "op"],
                        "additionalProperties": False,
                    }
                },
                "output": {
                    "schema": {
                        "type": "object",
                    },
                    "input_mapping": {"result": "$nodes.pick_result"},
                },
                "nodes": [
                    {
                        "id": "route_op",
                        "kind": "router",
                        "cases": {
                            "add": "$input.op == 'add'",
                            "sub": "$input.op == 'sub'",
                        },
                    },
                    {
                        "id": "do_add",
                        "kind": "python_code",
                        "input_mapping": {"x": "$input.x", "y": "$input.y"},
                        "code": """
return {"value": input["x"] + input["y"]}
""",
                        "output_mapping": {"value": "$.value"},
                    },
                    {
                        "id": "do_substruct",
                        "kind": "python_code",
                        "input_mapping": {"x": "$input.x", "y": "$input.y"},
                        "code": """
return {"value": input["x"] - input["y"]}
""",
                        "output_mapping": {"value": "$.value"},
                    },
                    {
                        "id": "pick_result",
                        "kind": "jq_transform",
                        "input_mapping": {
                            "add_result": "$nodes.do_add.value",
                            "sub_result": "$nodes.do_substruct.value",
                        },
                        # take either value from add or substruct branch
                        "code": "(.add_result // .sub_result)",
                        # keep output_mapping empty so output is {"result": <value>}
                        "output_mapping": {},
                    },
                ],
                "edges": [
                    {"from": "start", "to": "route_op"},
                    {"from": "route_op", "to": "do_add", "when_label": "add"},
                    {"from": "route_op", "to": "do_substruct", "when_label": "sub"},
                    {"from": "do_add", "to": "pick_result"},
                    {"from": "do_substruct", "to": "pick_result"},
                    {"from": "pick_result", "to": "end"},
                ],
            }
        )

        instance = WorkflowCompiler(compile_ctx=compile_ctx).compile(wf)

        final_add = await instance.ainvoke(
            {"input": {"x": 3, "y": 4, "op": "add"}}, config={"configurable": {}}
        )
        assert final_add["output"] == {"result": 7}

        final_sub = await instance.ainvoke(
            {"input": {"x": 3, "y": 4, "op": "sub"}}, config={"configurable": {}}
        )
        assert final_sub["output"] == {"result": -1}
