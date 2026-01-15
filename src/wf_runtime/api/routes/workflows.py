from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from wf_runtime.api.dependencies import get_workflow_executor
from wf_runtime.engine.executor import WorkflowExecutor
from wf_runtime.schema.validator import validate_instance

router = APIRouter()


class ValidateRequest(BaseModel):
    wf_spec: Dict[str, Any]
    input_data: Dict[str, Any] | None = None


class InvokeRequest(BaseModel):
    wf_spec: Dict[str, Any]
    input_data: Dict[str, Any]


@router.post("/workflow/validate")
async def validate_workflow(
    req: ValidateRequest,
    executor: WorkflowExecutor = Depends(get_workflow_executor),
) -> Dict[str, Any]:
    try:
        wf = await executor.validate_workflow(req.wf_spec)
        if req.input_data is not None:
            validate_instance(req.input_data, wf.input.schema_)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/workflow/invoke")
async def invoke_workflow(
    req: InvokeRequest,
    executor: WorkflowExecutor = Depends(get_workflow_executor),
) -> Dict[str, Any] | Any:
    try:
        output = await executor.ainvoke(req.wf_spec, req.input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return output
