from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from wf_runtime.api.dependencies import get_workflow_executor
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.schema.validator import validate_instance

router = APIRouter()


@router.post("/workflows/{workflow_id}/validate")
async def validate_workflow(
    wf_spec: str,
    input_data: Dict[str, Any] | None = None,
    executor: WorkflowExecutor = Depends(get_workflow_executor),
) -> Dict[str, Any]:
    try:
        wf = await executor.validate_workflow(wf_spec)
        if input_data is not None:
            validate_instance(input_data, wf.input.schema_)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/workflows/{workflow_id}/invoke")
async def invoke_workflow(
    wf_spec: str,
    input_data: Dict[str, Any],
    executor: WorkflowExecutor = Depends(get_workflow_executor),
) -> Dict[str, Any] | Any:
    try:
        output = await executor.ainvoke(wf_spec, input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return output
