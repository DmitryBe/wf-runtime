import pytest

from wf_runtime.backend.sandbox import SandboxRunError, SandboxRunnerImpl


class TestSandboxRunnerImpl:

    async def test_sandbox_runs_user_code_and_returns_result(self):
        runner = SandboxRunnerImpl()
        code = """
total = sum(item["price"] for item in input["items"])
if total > 200:
    return {"discount": 0.20}
elif total > 100:
    return {"discount": 0.10}
else:
    return {"discount": 0.0}
"""
        res = await runner.run(
            code=code,
            input_data={"items": [{"price": 120}, {"price": 30}]},
            timeout_s=2.0,
        )
        assert res == {"discount": 0.10}

    async def test_sandbox_runs_user_code_returns_const(self):
        runner = SandboxRunnerImpl()
        code = """
return "ok"
"""
        res = await runner.run(
            code=code,
            input_data={"items": [{"price": 120}, {"price": 30}]},
            timeout_s=2.0,
        )
        assert res == "ok"

    async def test_sandbox_runs_user_code_access_non_existing_key(self):
        runner = SandboxRunnerImpl()
        code = """
val = input["non_existing_key"]
return {"val": val}
"""
        with pytest.raises(SandboxRunError) as excinfo:
            await runner.run(
                code=code,
                input_data={"items": [{"price": 120}, {"price": 30}]},
                timeout_s=2.0,
            )
        assert "KeyError: 'non_existing_key'" in str(excinfo.value)

    async def test_sandbox_raises_on_user_exception_and_includes_printed_output(self):
        runner = SandboxRunnerImpl()
        code = """
raise ValueError("boom")
"""

        with pytest.raises(SandboxRunError) as excinfo:
            await runner.run(code=code, input_data={}, timeout_s=2.0)

        assert "Sandbox function failed" in str(excinfo.value)
        assert "ValueError" in str(excinfo.value)
