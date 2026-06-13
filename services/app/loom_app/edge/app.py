"""Edge HTTP API: REST for upload / build / ask / self-mod, SSE for streaming.

Single-tenant auth stub for the MVP (everything runs as the default tenant). SSE
is emitted directly from these handlers; Redis fan-out activates only when a
second process exists.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from loom_spec import AgentSpec
from sse_starlette.sse import EventSourceResponse

from loom_app import events, repo
from loom_app.config import DEFAULT_TENANT_ID
from loom_app.db import get_sessionmaker
from loom_app.edge.schemas import (
    AgentDetail,
    AgentSummary,
    AskRequest,
    BuildRequest,
    SelfModApplyRequest,
    SelfModProposeRequest,
    UploadResponse,
)
from loom_app.orchestrator import build_agent, selfmod
from loom_app.rag import ingest_document
from loom_app.runtime import run_agent

router = APIRouter(prefix="/api")
TENANT = DEFAULT_TENANT_ID


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ───────────────────────── knowledge base ─────────────────────────
@router.post("/kb/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    result = await ingest_document(
        data, file.filename or "document", file.content_type or "application/octet-stream", TENANT
    )
    return UploadResponse(
        document_id=result.document_id,
        kb_id=result.kb_id,
        filename=result.filename,
        num_pages=result.num_pages,
        num_chunks=result.num_chunks,
    )


# ───────────────────────── build (NL -> agent) ─────────────────────────
async def _build_stream(req: BuildRequest) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    if req.idempotency_key:
        async with sm() as s:
            prior = await repo.get_run_by_idem(s, TENANT, req.idempotency_key)
        if prior and prior["status"] == "done" and prior["result"]:
            res = prior["result"]
            yield events.ev("spec", **res)
            yield events.ev("done", agent_id=res.get("agent_id"), version=res.get("version"))
            return
        if prior:
            yield events.error("A build with this idempotency key is already in progress.")
            return

    async with sm() as s:
        run_id = await repo.create_run(
            s, TENANT, "build", {"request": req.request}, idempotency_key=req.idempotency_key
        )
        await s.commit()

    result: dict | None = None
    try:
        async for event in build_agent(req.request, TENANT, run_id):
            if event["event"] == "spec":
                result = json.loads(event["data"])
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done" if result else "error", result=result)
            await s.commit()
    except Exception as exc:  # surface and record
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()


@router.post("/agents/build")
async def agents_build(req: BuildRequest):
    return EventSourceResponse(_build_stream(req))


# ───────────────────────── ask (run an agent) ─────────────────────────
async def _ask_stream(agent_id: str, req: AskRequest) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        agent = await repo.get_agent(s, agent_id)
        spec_dict = await repo.get_spec(s, agent_id) if agent else None
    if spec_dict is None:
        yield events.error("Agent not found.")
        return

    spec = AgentSpec.model_validate(spec_dict)
    async with sm() as s:
        run_id = await repo.create_run(
            s, TENANT, "ask", {"message": req.message},
            agent_id=agent_id, agent_version=agent["current_version"],
        )
        await s.commit()

    answer: str | None = None
    try:
        async for event in run_agent(spec, req.message, tenant_id=TENANT, run_id=run_id):
            if event["event"] == "done":
                answer = json.loads(event["data"]).get("answer")
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done", result={"answer": answer})
            await s.commit()
    except Exception as exc:
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()


@router.post("/agents/{agent_id}/ask")
async def agents_ask(agent_id: str, req: AskRequest):
    return EventSourceResponse(_ask_stream(agent_id, req))


# ───────────────────────── self-modification ─────────────────────────
async def _selfmod_stream(agent_id: str, req: SelfModProposeRequest) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        run_id = await repo.create_run(
            s, TENANT, "selfmod", {"instruction": req.instruction}, agent_id=agent_id
        )
        await s.commit()
    try:
        async for event in selfmod.propose(agent_id, req.instruction, TENANT):
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done")
            await s.commit()
    except Exception as exc:
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()


@router.post("/agents/{agent_id}/selfmod/propose")
async def selfmod_propose(agent_id: str, req: SelfModProposeRequest):
    return EventSourceResponse(_selfmod_stream(agent_id, req))


@router.post("/agents/{agent_id}/selfmod/apply")
async def selfmod_apply(agent_id: str, req: SelfModApplyRequest) -> dict:
    try:
        return await selfmod.apply(agent_id, req.spec, TENANT)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ───────────────────────── read endpoints ─────────────────────────
@router.get("/agents", response_model=list[AgentSummary])
async def list_agents() -> list[AgentSummary]:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.list_agents(s, TENANT)
    return [
        AgentSummary(id=str(r["id"]), name=r["name"], current_version=r["current_version"])
        for r in rows
    ]


@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent(agent_id: str) -> AgentDetail:
    sm = get_sessionmaker()
    async with sm() as s:
        agent = await repo.get_agent(s, agent_id)
        spec = await repo.get_spec(s, agent_id) if agent else None
    if not agent or spec is None:
        raise HTTPException(404, "agent not found")
    return AgentDetail(
        id=str(agent["id"]), name=agent["name"],
        current_version=agent["current_version"], spec=spec,
    )
