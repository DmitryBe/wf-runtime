from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

PYTHON_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

JsonSchema = Union[str, Dict[str, Any]]


class NodeBase(BaseModel):
    """
    Common attributes for all nodes.
    """

    id: str = Field(..., description="Unique node ID")
    kind: str = Field(..., description="Node kind")
    name: Optional[str] = Field(default=None, description="Node name")

    @field_validator("id")
    def id_must_be_python_style(cls, v: str) -> str:
        if not PYTHON_ID_PATTERN.fullmatch(v):
            raise ValueError("id must be lowercase and snake_case (e.g. 'node_name')")
        return v


class IOConfig(BaseModel):
    input_mapping: Dict[str, Any] = Field(
        default_factory=dict, description="Input mapping, e.g. {'x': '$input.x'}"
    )
    output_mapping: Dict[str, Any] = Field(
        default_factory=dict,
        description=f"Output mapping, e.g. {{'x': '$.x', 'y': '$.y'}} to map specific fields from the node result or {{}} to map the entire node result",
    )


class Input(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    schema_: JsonSchema = Field(
        alias="schema",
        default={"type": "object"},
        description="Input schema, e.g. {'type': 'object', 'properties': {'x': {'type': 'integer'}}}",
    )


class Output(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    input_mapping: Dict[str, Any] = Field(
        description="Input mapping, e.g. {'x': '$result.x'}"
    )
    schema_: JsonSchema | None = Field(
        alias="schema",
        default={"type": "object"},
        description="Output schema, e.g. {'type': 'object', 'properties': {'x': {'type': 'integer'}}} The output shcmea must always be object, if properties are not specified, the entire node result is mapped",
    )


class NoopNode(NodeBase, IOConfig):
    kind: Literal["noop"] = "noop"


class LLMPromptPart(BaseModel):
    """
    A single multimodal prompt part.

    We use an object here (instead of a 2-tuple) because OpenAI's structured-output
    JSON Schema subset does not support tuple-style schemas (Pydantic emits
    `prefixItems`), which breaks `response_format` validation.
    """

    type: Literal["text", "image_url"] = Field(
        ..., description="Part type: 'text' or 'image_url'."
    )
    content: str = Field(
        ...,
        description=(
            "Part content.\n"
            "- For type='text': the text content.\n"
            "- For type='image_url': a URL or a data-URI (data:{mime};base64,{b64})."
        ),
    )


LLMPrompt = Union[str, List[LLMPromptPart]]


class LLMSchema(BaseModel):
    """
    Schema for LLM output.
    """

    type: str = Field(default="object", description="Schema type, e.g. 'object'")
    title: str = Field(..., description="Schema title, e.g. 'intent_classifier_output'")
    description: str = Field(
        ..., description="Schema description, e.g. 'Output of the intent classifier'"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Schema properties, e.g. {'intent': {'type': 'string', 'enum': ['positive', 'negative']}}",
    )
    required: List[str] | None = Field(
        default=None,
        description="Schema required fields (optional)",
    )


class LLMNode(NodeBase, IOConfig):
    kind: Literal["llm"] = "llm"
    model: str = Field(..., description="LLM model name, e.g. 'openai:gpt-4.1-mini'")
    model_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="LLM model parameters, e.g. {'temperature': 0.5}",
    )
    prompt: LLMPrompt = Field(
        ...,
        description=(
            "Prompt to send to the LLM.\n"
            "\n"
            "Supported formats:\n"
            "- Text-only: a plain string.\n"
            "- Multimodal: a list of objects with keys {type, content}.\n"
            "\n"
            "Text prompt example:\n"
            "```\n"
            "You are a strict classifier.\n"
            "Task: classify the user's text into exactly one label:\n"
            "- positive\n"
            "- negative\n"
            "Text:\n"
            "{text}\n"
            "```\n"
            "\n"
            "Multimodal prompt example:\n"
            "```\n"
            "[\n"
            '  {"type": "text", "content": "Analyze the image carefully and list 3 potential hygiene issues."},\n'
            '  {"type": "image_url", "content": "https://example.com/kitchen.jpg"},\n'
            "]\n"
            "```\n"
            "\n"
            "Image can also be passed as a data-URI, e.g.\n"
            "```\n"
            '{"type": "image_url", "content": f"data:{mime};base64,{b64}"}\n'
            "```"
        ),
    )
    output_schema: LLMSchema | None = Field(
        default=None,
        description="Output schema.",
    )

    @field_validator("prompt", mode="before")
    @classmethod
    def _normalize_prompt(cls, v: Any) -> Any:
        """
        Backward compatibility:
        - Accept legacy tuple form: [("text", "..."), ("image_url", "...")]
        - Accept OpenAI-style objects: {"type":"text","text":...} and
          {"type":"image_url","image_url":{"url":...}}
        Normalize into our canonical {type, content} objects.
        """

        if isinstance(v, list):
            out: list[Any] = []
            for part in v:
                # legacy: 2-tuple / 2-list
                if isinstance(part, (tuple, list)) and len(part) == 2:
                    t, c = part
                    out.append({"type": t, "content": c})
                    continue

                if isinstance(part, dict):
                    # already canonical
                    if "type" in part and "content" in part:
                        out.append(part)
                        continue

                    # OpenAI-ish variants
                    t = part.get("type")
                    if t == "text" and "text" in part:
                        out.append({"type": "text", "content": part["text"]})
                        continue
                    if t == "image_url":
                        if "url" in part:
                            out.append({"type": "image_url", "content": part["url"]})
                            continue
                        img = part.get("image_url")
                        if isinstance(img, dict) and "url" in img:
                            out.append({"type": "image_url", "content": img["url"]})
                            continue

                out.append(part)
            return out

        # Non-list (string / other) unchanged; Pydantic will validate.
        return v


class ToolNode(NodeBase, IOConfig):
    kind: Literal["tool"] = "tool"
    type: str  # tool registry key
    config: Dict[str, Any] = Field(default_factory=dict)


class JQNode(NodeBase, IOConfig):
    kind: Literal["jq_transform"] = "jq_transform"
    code: str = Field(
        ...,
        description="JQ code to execute. Example: {x: .x, doubled: (.x * 2)}",
    )


class PythonCodeNode(NodeBase, IOConfig):
    kind: Literal["python_code"] = "python_code"
    code: str = Field(
        ...,
        description=(
            "Python code to execute.\n"
            "Must return the result as a dict.\n"
            "Example:\n"
            "```\n"
            'x_doubled = input["x"] * 2\n'
            'text_upper = input["text"].upper()\n'
            'return {"x_doubled": x_doubled, "text_upper": text_upper}'
            "```"
        ),
    )
    timeout_s: float = Field(default=1.0, description="Timeout in seconds")


class RouterNode(NodeBase):
    kind: Literal["router"] = "router"
    cases: Dict[str, str] = Field(
        ...,
        description=(
            "Routing cases. Example: {'node_id': 'condition'} where condition is a python expression, example: '$input.x == 'a'' or '$nodes.y.z == 'b'', etc."
        ),
    )
    default: str | None = Field(
        default=None, description="Default node_id to take if no cases match"
    )


Node = Union[
    NoopNode,
    ToolNode,
    LLMNode,
    JQNode,
    PythonCodeNode,
    RouterNode,
]


class EdgeBase(BaseModel):
    from_: str = Field(..., alias="from", description="Source node_id")
    model_config = ConfigDict(populate_by_name=True)


class SimpleEdge(EdgeBase):
    to: str = Field(..., description="Target node_id")
    when_label: Optional[str] = Field(
        default=None, description="Condition to take this route"
    )


class EdgeRoute(BaseModel):
    to: str = Field(..., description="Target node_id")
    when_label: Optional[str] = Field(
        default=None, description="Condition to take this route"
    )


class BranchEdge(EdgeBase):
    routes: List[EdgeRoute] = Field(..., description="Routes to take")

    @model_validator(mode="after")
    def validate_routes(self):
        if not self.routes:
            raise ValueError("BranchEdge.routes must be non-empty")
        return self


Edge = Union[SimpleEdge, BranchEdge]


class Workflow(BaseModel):
    """
    Top-level workflow definition.
    """

    id: str = Field(..., description="Unique workflow ID")
    name: str | None = Field(default=None, description="Workflow name")
    version: int = Field(..., description="Workflow version")

    input: Input = Field(..., description="Workflow input schema")
    output: Output = Field(..., description="Workflow output schema")

    nodes: List[Node] = Field(
        ...,
        description="Workflow nodes. You should never create start or end nodes yourself, they are added by default.",
    )
    edges: List[Edge] = Field(
        ...,
        description=(
            "Workflow edges.\n"
            "Edges may reference the implicit 'start' and 'end' nodes (do not add them to `nodes`).\n"
            'Example: [{"from": "start", "to": "node_id"}, {"from": "node_id", "to": "end"}]'
        ),
    )
    fail_fast: bool = Field(
        default=True, description="Whether to fail fast the workflow if any node fails"
    )

    @model_validator(mode="before")
    @classmethod
    def require_output(cls, data: Any):
        """
        Validate the workflow.
        """
        if isinstance(data, dict) and "id" not in data:
            raise ValueError("Workflow must have an 'id' section.")
        if isinstance(data, dict) and "version" not in data:
            raise ValueError("Workflow must have a 'version' section.")
        if isinstance(data, dict) and "input" not in data:
            raise ValueError("Workflow must have an 'input' section.")
        if isinstance(data, dict) and "output" not in data:
            raise ValueError("Workflow must have an 'output' section.")
        return data

    @field_validator("nodes")
    def unique_node_ids(cls, nodes: List[Node]):
        ids = [n.id for n in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate node IDs found in workflow")
        return nodes

    @field_validator("edges")
    def validate_edges(cls, edges: List[Edge], info: ValidationInfo):
        nodes = (info.data or {}).get("nodes", [])
        node_ids = {n.id for n in nodes}
        node_ids.add("start")  # allow start → node
        node_ids.add("end")  # allow node → end

        for e in edges:
            if e.from_ not in node_ids:
                raise ValueError(f"Edge from unknown node '{e.from_}'")
            if isinstance(e, SimpleEdge):
                if e.to != "end" and e.to not in node_ids:
                    raise ValueError(f"Edge to unknown node '{e.to}'")
            else:
                # BranchEdge: validate every route target
                for r in e.routes:
                    if r.to != "end" and r.to not in node_ids:
                        raise ValueError(f"Edge route to unknown node '{r.to}'")
        return edges

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)
