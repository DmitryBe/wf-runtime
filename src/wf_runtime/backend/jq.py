from __future__ import annotations

from typing import Any, Dict

import jq


class JQRunnerImpl:
    """
    Implementation of JQRunner using the jq library.
    """

    def run(self, *, program: str, input_data: Dict[str, Any]) -> Any:
        """
        Execute a JQ program on input data.

        Args:
            program: JQ program string
            input_data: Input data dictionary

        Returns:
            Result of JQ execution
        """
        compiled = jq.compile(program)
        result = compiled.input(input_data).first()
        return result
