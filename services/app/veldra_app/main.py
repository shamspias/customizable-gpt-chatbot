"""FastAPI application — the single MVP process (edge + orchestrator + runtime + rag).

Run with: uvicorn veldra_app.main:app --reload
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from veldra_app.config import get_settings
from veldra_app.edge import auth_router, plugin_router, router
from veldra_app.tracing import setup_tracing

# Built Vue SPA (present in Docker / after `npm run build`); when absent (pure dev),
# the Vite dev server on :5173 serves the UI instead.
WEB_DIST = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"

_log = logging.getLogger("veldra.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    app = FastAPI(title="Veldra", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Tag every request with a correlation id and log method/path/status/latency."""
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _log.exception("request_failed rid=%s %s %s", rid, request.method, request.url.path)
            raise
        dur_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        if request.url.path.startswith("/api/"):
            _log.info("rid=%s %s %s -> %s %.1fms",
                      rid, request.method, request.url.path, response.status_code, dur_ms)
        return response

    app.add_middleware(
        CORSMiddleware,
        # Explicit allow-list (app origin + the Vite dev server in local) — never the
        # wildcard now that requests carry a bearer token.
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(auth_router)  # /api/auth/* + /api/setup/*
    app.include_router(plugin_router)  # /api/plugins/*
    app.include_router(router)  # /api/* — registered before the SPA mount so it wins
    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
