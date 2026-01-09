from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from RestrictedPython import compile_restricted
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.Utilities import utility_builtins


@dataclass
class SandboxRunError(Exception):
    message: str
    printed: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return self.message


class SandboxRunnerImpl:
    """
    RestrictedPython-based runner.

    Important limitation: RestrictedPython is not a full OS sandbox.
    Use containers/subprocess for hard isolation + hard-kill timeouts.
    """

    def __init__(self) -> None:
        self._builtins = _safe_builtins()

    async def run(
        self, *, code: str, input_data: Dict[str, Any], timeout_s: float
    ) -> Dict[str, Any]:
        wrapped = _wrap_user_code_as_fn(code, fn_name="user_main")

        try:
            compiled = compile_restricted(
                wrapped, filename="<sandboxed_python_code>", mode="exec"
            )
        except SyntaxError as e:
            raise SandboxRunError(
                "RestrictedPython compilation failed",
                details={"errors": e.args},
            ) from e

        safe_globals: Dict[str, Any] = {
            "__builtins__": self._builtins,
            # Guards (per RestrictedPython docs)
            "_getattr_": safer_getattr,
            "_getitem_": default_guarded_getitem,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_write_": full_write_guard,
            # Captured print
            "_print_": PrintCollector,
        }
        safe_locals: Dict[str, Any] = {}

        def _execute_sync() -> Dict[str, Any]:
            try:
                exec(compiled, safe_globals, safe_locals)  # noqa: S102
            except Exception as e:
                printed = ""
                try:
                    printed = (
                        safe_locals.get("_print", None) and safe_locals["_print"]()
                    )
                except Exception:
                    pass
                raise SandboxRunError(
                    f"Sandbox exec failed: {type(e).__name__}: {e}",
                    printed=printed,
                )

            fn = safe_locals.get("user_main") or safe_globals.get("user_main")
            if not callable(fn):
                printed = ""
                try:
                    printed = (
                        safe_locals.get("_print", None) and safe_locals["_print"]()
                    )
                except Exception:
                    pass
                raise SandboxRunError(
                    "Sandbox code did not define callable user_main(input)",
                    printed=printed,
                )

            try:
                result = fn(input_data)
            except Exception as e:
                printed = ""
                try:
                    printed = (
                        safe_locals.get("_print", None) and safe_locals["_print"]()
                    )
                except Exception:
                    pass
                raise SandboxRunError(
                    f"Sandbox function failed: {type(e).__name__}: {e}",
                    printed=printed,
                )

            printed = ""
            try:
                printed = safe_locals.get("_print", None) and safe_locals["_print"]()
            except Exception:
                pass

            if isinstance(result, dict):
                out: Dict[str, Any] = dict(result)
            else:
                out = result

            if printed:
                out["_printed"] = printed
            return out

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, _execute_sync)

        try:
            return await asyncio.wait_for(fut, timeout=timeout_s)
        except asyncio.TimeoutError as e:
            raise SandboxRunError(
                f"Sandbox execution timed out after {timeout_s} seconds"
            ) from e


def _indent(code: str, spaces: int = 4) -> str:
    pad = " " * spaces
    return "\n".join(
        (pad + line if line.strip() else line) for line in code.splitlines()
    )


def _wrap_user_code_as_fn(code: str, fn_name: str = "user_main") -> str:
    # Allows YAML authors to write top-level `return {...}`.
    return f"def {fn_name}(input):\n{_indent(code)}\n"


def _safe_builtins() -> Dict[str, Any]:
    allowed = {
        "dict": dict,
        "list": list,
        "set": set,
        "tuple": tuple,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "sorted": sorted,
        "range": range,
        "enumerate": enumerate,
        "abs": abs,
        "all": all,
        "any": any,
        "zip": zip,
        "map": map,
        "filter": filter,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
    }

    b = dict(utility_builtins)
    b.update(allowed)
    b.pop("__import__", None)  # no imports
    return b
