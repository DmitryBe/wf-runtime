from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from wf_runtime.engine.state import WorkflowState


class MappingError(ValueError):
    pass


@dataclass(frozen=True)
class ResolveOptions:
    """
    Controls how strict resolving is.
    - strict: if True, missing keys raise; otherwise returns None
    """

    strict: bool = True


def resolve_expr(
    state: WorkflowState, expr: Any, *, options: ResolveOptions = ResolveOptions()
) -> Any:
    """
    Resolve:
      - constants (non-str or str not starting with "$") -> returned as-is
      - $input
      - $input.foo.bar
      - $nodes.node_id.key
      - $nodes.node_id.key.deep
      - $state.some_key
    """
    if not isinstance(expr, str) or not expr.startswith("$"):
        return expr

    def _get_path(obj: Any, path: list[str]) -> Any:
        cur = obj
        for p in path:
            if isinstance(cur, dict):
                if p in cur:
                    cur = cur[p]
                elif options.strict:
                    raise MappingError(
                        f"Missing key '{p}' while resolving path {'.'.join(path)}"
                    )
                else:
                    return None
            else:
                # allow attribute access for pydantic models / objects if needed
                if hasattr(cur, p):
                    cur = getattr(cur, p)
                elif options.strict:
                    raise MappingError(
                        f"Missing attribute '{p}' while resolving path {'.'.join(path)}"
                    )
                else:
                    return None
        return cur

    if expr == "$input":
        return state.get("input")

    if expr.startswith("$input."):
        path = expr[len("$input.") :].split(".")
        return _get_path(state.get("input"), path)

    if expr.startswith("$nodes."):
        rest = expr[len("$nodes.") :]
        parts = rest.split(".")
        if len(parts) == 1:
            return (state.get("data") or {}).get(parts[0])

        node_id = parts[0]
        path = parts[1:]
        node_out = (state.get("data") or {}).get(node_id, {})
        return _get_path(node_out, path)

    if expr.startswith("$state."):
        key = expr[len("$state.") :]
        if key in state:
            return state[key]  # type: ignore[index]
        if options.strict:
            raise MappingError(f"Missing state key: {key}")
        return None

    raise MappingError(f"Unsupported expression: {expr}")


def resolve_inputs(
    state: WorkflowState,
    input_mapping: Mapping[str, Any],
    *,
    options: ResolveOptions = ResolveOptions(),
) -> Dict[str, Any]:
    """
    Resolves a node's input_mapping into a concrete dict passed to the node executor.
    """
    resolved: Dict[str, Any] = {}
    for k, v in input_mapping.items():
        resolved[k] = resolve_expr(state, v, options=options)
    return resolved


def apply_output_mapping(
    result: Any, output_mapping: Mapping[str, Any]
) -> Dict[str, Any]:
    """
    Maps raw node result -> standardized node outputs dict.

    Conventions:
      - If output_mapping empty: result
      - Special tokens:
          "$result" or "$tool_result" or "$jq_result" or "$code_result" -> raw result
      - JSONPath-lite:
          "$.field.subfield" -> read from dict result
    """
    if not output_mapping:
        return result

    def _get_from_result(obj: Any, path: list[str]) -> Any:
        cur = obj
        for p in path:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        return cur

    out: Dict[str, Any] = {}
    for out_key, spec in output_mapping.items():
        if spec in ("$result", "$tool_result", "$jq_result", "$code_result"):
            out[out_key] = result
        elif isinstance(spec, str) and spec.startswith("$."):
            out[out_key] = _get_from_result(result, spec[2:].split("."))
        else:
            # allow constants or user-provided literal structures
            out[out_key] = spec
    return out


def write_node_outputs(
    state: WorkflowState,
    node_id: str,
    outputs: Dict[str, Any],
) -> WorkflowState:
    """
    Writes node outputs into state["data"][node_id].

    Important: this returns a *partial state update* (only keys that changed).
    Returning the full state would cause parallel nodes to "rewrite" unrelated
    keys like `input`, which LangGraph will reject unless those keys have a
    reducer.
    """
    return {
        "data": {node_id: outputs},
        "last_node": node_id,
    }


def write_error(
    state: WorkflowState,
    node_id: str,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    return {
        "errors": [
            {
                "node_id": node_id,
                "type": error_type,
                "message": message,
                "details": details or {},
            }
        ],
        "last_node": node_id,
    }
