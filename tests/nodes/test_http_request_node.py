import wf_runtime.engine.nodes.http_request as http_request_node
from wf_runtime.dsl.models import HttpRequestNode
from wf_runtime.engine.nodes.base import CompileContext, RuntimeContext


class TestHttpRequestNode:

    async def test_http_get_request(self):

        node_def = HttpRequestNode.model_validate(
            {
                "id": "http_request",
                "kind": "http_request",
                "timeout_s": 5,
                "input_mapping": {
                    "url": "https://httpbin.org/get",
                    "method": "GET",
                    "headers": {},
                    # will be passed via url
                    "key1": "value1",
                    "key2": "value2",
                },
            }
        )

        executor = http_request_node.make_http_request_executor(
            node_def, CompileContext()
        )
        update = await executor(
            {"input": {"text": "some data"}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )

        result = update["data"].get("http_request")
        assert result["ok"] == True
        assert result.get("body_json").get("args") == {
            "key1": "value1",
            "key2": "value2",
        }

    async def test_http_post_request(self):

        node_def = HttpRequestNode.model_validate(
            {
                "id": "http_request",
                "kind": "http_request",
                "timeout_s": 5,
                "input_mapping": {
                    "url": "https://httpbin.org/post",
                    "method": "POST",
                    "headers": {
                        "content-type": "application/json",
                    },
                    # will be passed via body
                    "key1": "value1",
                    "key2": "value2",
                },
            }
        )

        executor = http_request_node.make_http_request_executor(
            node_def, CompileContext()
        )
        update = await executor(
            {"input": {"text": "some data"}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )

        result = update["data"].get("http_request")
        assert result["ok"] == True
        assert result.get("body_json").get("json") == {
            "key1": "value1",
            "key2": "value2",
        }

    async def test_http_get_image(self):

        node_def = HttpRequestNode.model_validate(
            {
                "id": "http_request",
                "kind": "http_request",
                "timeout_s": 5,
                "input_mapping": {
                    "url": "https://media.hswstatic.com/eyJidWNrZXQiOiJjb250ZW50Lmhzd3N0YXRpYy5jb20iLCJrZXkiOiJnaWZcL3NodXR0ZXJzdG9jay0yMjc4Nzc2MTg3LWhlcm8uanBnIiwiZWRpdHMiOnsicmVzaXplIjp7IndpZHRoIjo4Mjh9fX0=",
                    "method": "GET",
                },
            }
        )

        executor = http_request_node.make_http_request_executor(
            node_def, CompileContext()
        )
        update = await executor(
            {"input": {"x": 21}, "data": {}, "errors": []},
            RuntimeContext(configurable={}),
        )

        result = update["data"].get("http_request")
        assert result["ok"] == True
