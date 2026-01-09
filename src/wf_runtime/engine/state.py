from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, TypedDict


def _pick_right[T](left: T, right: T) -> T:
    """
    Reducer used by LangGraph when multiple parallel branches update the same key.
    """

    return right


def _merge_dicts(
    left: Dict[str, Any] | None, right: Dict[str, Any] | None
) -> Dict[str, Any]:
    """
    Safe dict merge reducer.
    Keeps keys from both sides; right wins on conflicts.
    """

    merged: Dict[str, Any] = {}
    if left:
        merged.update(left)
    if right:
        merged.update(right)
    return merged


class WorkflowState(TypedDict, total=False):
    # workflow input
    input: Dict[str, Any]
    # nodes outputs
    data: Annotated[Dict[str, Any], _merge_dicts]
    # last executed node
    last_node: Annotated[str | None, _pick_right]
    # workflow result
    output: Dict[str, Any]
    # errors
    errors: Annotated[List[Dict[str, Any]], operator.add]
