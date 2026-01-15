from __future__ import annotations

from fastapi import FastAPI

from wf_runtime.api.routes.health import router as health_router
from wf_runtime.api.routes.workflows import router as workflows_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="wf-runtime",
        version="0.1.0",
    )

    app.include_router(health_router, tags=["health"])
    app.include_router(workflows_router, tags=["workflows"])

    return app
