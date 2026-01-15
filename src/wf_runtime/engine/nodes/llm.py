from __future__ import annotations

import os
from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

from wf_runtime.dsl.models import LLMNode, LLMPrompt, LLMPromptPart
from wf_runtime.engine.mappings import (
    apply_output_mapping,
    resolve_inputs,
    write_error,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


def make_llm_executor(node_def: LLMNode, compile_ctx: CompileContext) -> NodeExecutor:
    """
    LLM node expects:
      config:
        prompt: str OR template str (we'll do simple format with resolved inputs)
        output_schema: dict (JSON schema for structured output)
        model_params: dict (optional, forwarded to client)
    """
    node_id = node_def.id

    llm: BaseChatModel = init_chat_model(node_def.model, **node_def.model_params)
    if node_def.output_schema:
        llm = llm.with_structured_output(
            schema=node_def.output_schema.model_dump(exclude_none=True)
        )

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        # NOTE: we should add a more generic way to check for required environment variables
        if not os.getenv("OPENAI_API_KEY"):
            return write_error(
                state, node_id, "missing_dependency", "OPENAI_API_KEY is not set"
            )

        try:
            # Use default strict resolving semantics (same as most other nodes).
            inputs: Dict[str, Any] = resolve_inputs(state, node_def.input_mapping)
            msg = _format_msg(node_def.prompt, inputs)
            result = await llm.ainvoke([msg])
            if isinstance(result, AIMessage):
                result = result.content
            outputs = apply_output_mapping(result, node_def.output_mapping)
            if compile_ctx.emit_event:
                await compile_ctx.emit_event(
                    {
                        "type": "node_completed",
                        "node_id": node_id,
                        "kind": "llm",
                    }
                )
            return write_node_outputs(state, node_id, outputs)
        except KeyError as e:
            return write_error(
                state,
                node_id,
                "prompt_format_error",
                f"Missing key for prompt template: {e}",
            )
        except Exception as e:
            return write_error(state, node_id, "llm_error", str(e))

    return _exec


def _format_msg(prompt: LLMPrompt, inputs: Dict[str, Any]) -> HumanMessage:
    """
    Formats a prompt into a HumanMessage.
    """

    if isinstance(prompt, str):
        return HumanMessage(content=prompt.format(**inputs))

    if isinstance(prompt, list):
        content: list[dict[str, Any]] = []
        for part in prompt:
            # Be tolerant if a raw dict slipped through (e.g. constructed directly)
            if isinstance(part, dict):
                t = part.get("type")
                v = part.get("content") or part.get("text") or part.get("url")
            else:
                part = part  # type: ignore[no-redef]
                if isinstance(part, LLMPromptPart):
                    t = part.type
                    v = part.content
                else:
                    raise ValueError(f"Unsupported prompt part: {part!r}")

            if t == "text":
                content.append({"type": "text", "text": str(v).format(**inputs)})
            elif t == "image_url":
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": str(v).format(**inputs)},
                        # url or "data:{mime};base64,{b64}"
                    }
                )
            else:
                raise ValueError(f"Unsupported multimodal prompt part type: {t}")

        return HumanMessage(content=content)
