from __future__ import annotations

import asyncio
import base64
import json
from typing import Any, Dict

import aiohttp

from wf_runtime.dsl.models import HttpRequestNode
from wf_runtime.engine.mappings import (
    apply_output_mapping,
    resolve_inputs,
    write_error,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


def make_http_request_executor(
    node_def: HttpRequestNode, compile_ctx: CompileContext
) -> NodeExecutor:
    """
    HttpRequest node makes an HTTP request.
    """
    node_id = node_def.id

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        try:
            inputs: Dict[str, Any] = resolve_inputs(state, node_def.input_mapping)

            url = _deep_format(inputs.get("url"), inputs)
            if not isinstance(url, str):
                return write_error(
                    state,
                    node_id,
                    "http_request_error",
                    f"url must resolve to a string, got: {type(url).__name__}",
                )

            method = (inputs.get("method") or "GET").upper()

            headers = {k: v for k, v in inputs.get("headers", {}).items()}
            body = {
                k: v for k, v in inputs.items() if k not in ("url", "method", "headers")
            }

            params = None
            json_body = None
            if method in ("GET", "DELETE"):
                # Common convention: treat "body" as query params for GET/DELETE.
                params = body if isinstance(body, dict) and body else None
            else:
                # POST, PUT, PATCH
                json_body = body if isinstance(body, dict) and body else None

            timeout = aiohttp.ClientTimeout(total=float(node_def.timeout_s))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers={str(k): str(v) for k, v in headers.items()},
                    params=params,
                    json=json_body,
                ) as resp:
                    body_bytes = await resp.read()
                    content_type = resp.headers.get("Content-Type", "")

                    result: Dict[str, Any] = {
                        "ok": 200 <= resp.status < 300,
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        **_parse_response_body(
                            body=body_bytes, content_type=content_type
                        ),
                    }

                    if not result["ok"]:
                        return write_error(
                            state,
                            node_id,
                            "http_request_error",
                            f"HTTP {resp.status} for {url}",
                            details=result,
                        )

                    outputs = apply_output_mapping(result, node_def.output_mapping)
                    if compile_ctx.emit_event:
                        await compile_ctx.emit_event(
                            {
                                "type": "node_completed",
                                "node_id": node_id,
                                "kind": "http_request",
                            }
                        )
                    return write_node_outputs(state, node_id, outputs)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return write_error(state, node_id, "http_request_error", str(e))
        except Exception as e:
            return write_error(state, node_id, "http_request_error", str(e))

    return _exec


def _deep_format(value: Any, vars: Dict[str, Any]) -> Any:
    """
    Recursively format strings using Python's `.format(**vars)`.
    Non-strings are returned as-is.
    """
    if isinstance(value, str):
        return value.format(**vars)
    if isinstance(value, dict):
        return {k: _deep_format(v, vars) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_format(v, vars) for v in value]
    return value


def _parse_response_body(*, body: bytes, content_type: str) -> Dict[str, Any]:
    """
    Return a JSON-friendly representation of the response body.
    Prefer JSON when possible; otherwise UTF-8 text; otherwise base64.
    """
    out: Dict[str, Any] = {"body_bytes_len": len(body)}

    ct = (content_type or "").lower()
    looks_json = "application/json" in ct or ct.endswith("+json")

    if looks_json:
        try:
            out["body_json"] = json.loads(body.decode("utf-8"))
            return out
        except Exception:
            # fall through to text/base64
            pass

    try:
        out["body_text"] = body.decode("utf-8")
        return out
    except UnicodeDecodeError:
        out["body_b64"] = base64.b64encode(body).decode("utf-8")
        return out
