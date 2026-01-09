from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Dict

from wf_runtime.dsl.models import RouterNode
from wf_runtime.engine.mappings import (
    ResolveOptions,
    resolve_expr,
    write_error,
    write_node_outputs,
)
from wf_runtime.engine.nodes.base import CompileContext, NodeExecutor, RuntimeContext
from wf_runtime.engine.state import WorkflowState


class RouterEvalError(ValueError):
    pass


@dataclass(frozen=True)
class RouterEnv:
    """
    View of state exposed to router conditions.
    """

    input: Any
    nodes: Dict[str, Dict[str, Any]]
    state: Dict[str, Any]


ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
)


def _ensure_safe_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise RouterEvalError(
                f"Unsupported expression element: {type(node).__name__}"
            )


def _eval_ast(node: ast.AST, env: Dict[str, Any]) -> Any:
    """
    Minimal safe evaluator for a subset of python expressions.
    """
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, env)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        return env.get(node.id)

    if isinstance(node, ast.UnaryOp):
        v = _eval_ast(node.operand, env)
        if isinstance(node.op, ast.Not):
            return not bool(v)
        raise RouterEvalError("Unsupported unary op")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not bool(_eval_ast(v, env)):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for v in node.values:
                if bool(_eval_ast(v, env)):
                    return True
            return False
        raise RouterEvalError("Unsupported bool op")

    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, env)
        right = _eval_ast(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise RouterEvalError("Unsupported binary op")

    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left, env)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval_ast(comp, env)
            ok: bool
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            else:
                raise RouterEvalError("Unsupported compare op")
            if not ok:
                return False
            left = right
        return True

    raise RouterEvalError(f"Unsupported node type: {type(node).__name__}")


def eval_condition(condition: str, state: WorkflowState) -> bool:
    """
    Supports:
      - "else" keyword
      - references like "$input.x == 'a'" (we resolve $input.x into env vars first)
      - env vars: input, nodes, state (dict-like)
    """
    if condition.strip() == "else":
        return True

    expr = condition.strip()

    # Allow `$input.*` alias in conditions (docs use `$input`, core uses `$input`).
    expr = re.sub(r"\$input(\.|$)", r"$input\1", expr)

    # Replace `$input.*`, `$nodes.*.*`, `$state.*` references in the expression
    # with injected python variables (ref_0, ref_1, ...), then eval a safe AST.
    #
    # This allows writing conditions like:
    #   "$input.op == 'add'"
    # without needing subscript/attr access in the AST.
    ref_pat = re.compile(
        r"\$(?:input(?:\.[A-Za-z0-9_]+)+|nodes\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+|state\.[A-Za-z0-9_]+)"
    )

    # Provide environment with common roots
    env = {
        # NOTE: the workflow state uses "input" (singular). Keep "input" for
        # backwards-compatibility with earlier docs.
        "input": state.get("input"),
        "nodes": state.get("data") or {},
        "state": dict(state),
    }

    refs: Dict[str, Any] = {}

    def _sub(m: re.Match) -> str:
        token = m.group(0)
        key = f"ref_{len(refs)}"
        # For router conditions we want missing data to be falsy, not fatal.
        refs[key] = resolve_expr(state, token, options=ResolveOptions(strict=False))
        return key

    rewritten = ref_pat.sub(_sub, expr)
    env.update(refs)

    tree = ast.parse(rewritten, mode="eval")
    _ensure_safe_ast(tree)
    return bool(_eval_ast(tree, env))


def pick_route(
    cases: Dict[str, str], default_label: str | None, state: WorkflowState
) -> str | None:
    """
    cases: {"label": "condition"} where condition is a python expression, example: "$input.x == 'a'" or "$nodes.y.z == 'b', etc."
    Returns: label of first match
    """
    for label, condition in cases.items():
        if eval_condition(condition, state):
            return label
    return default_label


def make_router_executor(
    node_def: RouterNode, compile_ctx: CompileContext
) -> NodeExecutor:
    """
    Router node expects:
      cases: {"label": "condition"} where condition is a python expression, example: "$input.x == 'a'" or "$nodes.y.z == 'b', etc."
    """
    node_id = node_def.id

    async def _exec(
        state: WorkflowState, _runtime_ctx: RuntimeContext
    ) -> WorkflowState:
        try:
            label = pick_route(node_def.cases, node_def.default, state)
            if label is None:
                return write_error(state, node_id, "router_error", "No route selected")

            if compile_ctx.emit_event:
                await compile_ctx.emit_event(
                    {
                        "type": "node_completed",
                        "node_id": node_id,
                        "kind": "router",
                        "route": label,
                    }
                )
            return write_node_outputs(state, node_id, {"label": label})
        except Exception as e:
            return write_error(state, node_id, "router_error", str(e))

    return _exec
