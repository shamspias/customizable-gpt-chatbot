"""FastAPI application — the single MVP process (edge + orchestrator + runtime + rag).

Run with: uvicorn veldra_app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from veldra_app.config import get_settings
from veldra_app.edge import auth_router, router
from veldra_app.tracing import setup_tracing

# Built Vue SPA (present in Docker / after `npm run build`); when absent (pure dev),
# the Vite dev server on :5173 serves the UI instead.
WEB_DIST = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Veldra", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        # Explicit allow-list (app origin + the Vite dev server in local) — never the
        # wildcard now that requests carry a bearer token.
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)  # /api/auth/* + /api/setup/*
    app.include_router(router)  # /api/* — registered before the SPA mount so it wins
    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
