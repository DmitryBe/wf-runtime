from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Protocol

from wf_runtime.engine.state import WorkflowState


class JQRunner(Protocol):
    """
    Interface for JQ execution.
    """

    def run(self, *, program: str, input_data: Dict[str, Any]) -> Any: ...


class SandboxRunner(Protocol):
    """
    Interface for sandboxed python execution.
    """

    async def run(
        self, *, code: str, input_data: Dict[str, Any], timeout_s: float
    ) -> Dict[str, Any]: ...


@dataclass
class CompileContext:
    """
    Compile-time dependencies that are reused across all graph executions.
    These are provided when constructing the graph and remain constant.
    """

    jq: JQRunner | None = None
    sandbox: SandboxRunner | None = None
    emit_event: Callable[[Dict[str, Any]], Awaitable[None]] | None = None


@dataclass
class RuntimeContext:
    """
    Runtime dependencies injected into nodes for each graph request.
    Created per execution and contains request-specific data.
    """

    configurable: Dict[str, Any] | None = None


NodeExecutor = Callable[[WorkflowState, RuntimeContext], Awaitable[WorkflowState]]
