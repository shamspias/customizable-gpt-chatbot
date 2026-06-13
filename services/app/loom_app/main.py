"""FastAPI application — the single MVP process (edge + orchestrator + runtime + rag).

Run with: uvicorn loom_app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from loom_app.config import get_settings
from loom_app.edge import router
from loom_app.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Loom", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        # MVP: permissive for local dev (Vue on :5173). Tighten at v1 with real auth.
        allow_origins=["*"] if settings.env == "local" else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
