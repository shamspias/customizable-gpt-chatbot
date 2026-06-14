"""Edge HTTP API: REST for upload / build / ask / self-mod, SSE for streaming.

Single-tenant auth stub for the MVP (everything runs as the default tenant). SSE
is emitted directly from these handlers; Redis fan-out activates only when a
second process exists.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse
from veldra_spec import AgentSpec

from veldra_app import events, faust, learning, repo
from veldra_app.config import DEFAULT_TENANT_ID
from veldra_app.db import get_sessionmaker
from veldra_app.edge.schemas import (
    AgentDetail,
    AgentSummary,
    AskRequest,
    BuildRequest,
    DocEditRequest,
    FeedbackRequest,
    IdsRequest,
    KbCreateRequest,
    KbUpdateRequest,
    ReflectRequest,
    SelfModApplyRequest,
    SelfModProposeRequest,
    TagsRequest,
    UploadResponse,
    UrlIngestRequest,
    WorkflowSaveRequest,
)
from veldra_app.orchestrator import build_agent, selfmod
from veldra_app.rag import ingest_document
from veldra_app.rag.ingest import ingest_url, reingest_text
from veldra_app.runtime import execute

router = APIRouter(prefix="/api")
TENANT = DEFAULT_TENANT_ID


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ───────────────────────── knowledge bases ─────────────────────────
def _ingest_response(result) -> UploadResponse:
    return UploadResponse(
        document_id=result.document_id, kb_id=result.kb_id, filename=result.filename,
        num_pages=result.num_pages, num_chunks=result.num_chunks,
    )


@router.get("/kb")
async def list_kbs() -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_kbs(s, TENANT)


@router.post("/kb")
async def create_kb(req: KbCreateRequest) -> dict:
    sm = get_sessionmaker()
    cfg = req.model_dump(exclude={"name"}, exclude_none=True)
    async with sm() as s:
        kb_id = await repo.create_kb(s, TENANT, req.name, **cfg)
        await s.commit()
        kb = await repo.get_kb(s, kb_id)
    return kb or {"id": kb_id, "name": req.name}


@router.get("/kb/{kb_id}")
async def get_kb(kb_id: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        kb = await repo.get_kb(s, kb_id)
    if kb is None:
        raise HTTPException(404, "knowledge base not found")
    return kb


@router.patch("/kb/{kb_id}")
@router.put("/kb/{kb_id}")
async def update_kb(kb_id: str, req: KbUpdateRequest) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        if await repo.get_kb(s, kb_id) is None:
            raise HTTPException(404, "knowledge base not found")
        await repo.update_kb(s, kb_id, **req.model_dump(exclude_none=True))
        await s.commit()
        return await repo.get_kb(s, kb_id)


@router.delete("/kb/{kb_id}")
async def delete_kb(kb_id: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_kb(s, kb_id)
        await s.commit()
    return {"deleted": kb_id}


@router.get("/kb/{kb_id}/documents")
async def list_documents(kb_id: str) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_documents(s, kb_id)


@router.post("/kb/{kb_id}/upload", response_model=UploadResponse)
async def upload_to_kb(kb_id: str, file: UploadFile = File(...)) -> UploadResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    result = await ingest_document(
        data, file.filename or "document",
        file.content_type or "application/octet-stream", TENANT, kb_id=kb_id,
    )
    return _ingest_response(result)


@router.post("/kb/{kb_id}/ingest-url", response_model=UploadResponse)
async def ingest_from_url(kb_id: str, req: UrlIngestRequest) -> UploadResponse:
    """Fetch a web page and index it into the KB (web page index)."""
    try:
        result = await ingest_url(req.url, TENANT, kb_id=kb_id)
    except Exception as exc:
        raise HTTPException(400, f"could not ingest URL: {exc}") from exc
    return _ingest_response(result)


@router.get("/kb/{kb_id}/documents/{doc_id}")
async def get_document(kb_id: str, doc_id: str) -> dict:
    """Document detail + editable text + the page-index tree."""
    sm = get_sessionmaker()
    async with sm() as s:
        doc = await repo.get_document(s, doc_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        text = await repo.get_document_text(s, doc_id)
        page_index = await repo.get_page_index(s, doc_id)
    return {"document": doc, "text": text, "page_index": page_index}


@router.put("/kb/{kb_id}/documents/{doc_id}", response_model=UploadResponse)
async def edit_document(kb_id: str, doc_id: str, req: DocEditRequest) -> UploadResponse:
    """Replace a saved document's content with edited text and re-embed it."""
    try:
        result = await reingest_text(doc_id, req.text, TENANT)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _ingest_response(result)


@router.post("/kb/{kb_id}/documents/delete")
async def delete_documents(kb_id: str, req: IdsRequest) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_documents(s, kb_id, req.ids)
        await s.commit()
    return {"deleted": n}


@router.delete("/kb/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_document(s, doc_id)
        await s.commit()
    return {"deleted": doc_id}


@router.post("/kb/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    """Upload to the default KB (kept for convenience / the CLI)."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    result = await ingest_document(
        data, file.filename or "document", file.content_type or "application/octet-stream", TENANT
    )
    return _ingest_response(result)


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
        # Inject episodic memory: the agent applies what it has learned (Reflexion).
        lessons = await repo.list_lessons(s, agent_id, limit=10)
    if lessons:
        spec = spec.model_copy(
            update={"system_prompt": spec.system_prompt + learning.lessons_block(lessons)}
        )

    # Tell the client which run this is, so it can attach 👍/👎 feedback.
    yield events.ev("run", run_id=run_id)
    answer: str | None = None
    try:
        async for event in execute(
            spec, req.message, tenant_id=TENANT, run_id=run_id, history=req.history
        ):
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


@router.put("/agents/{agent_id}/workflow")
async def save_workflow(agent_id: str, req: WorkflowSaveRequest) -> dict:
    """Persist a workflow graph edited in the visual builder (new spec version)."""
    try:
        return await selfmod.set_workflow(agent_id, req.graph, TENANT)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ───────────────────────── read endpoints ─────────────────────────
@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(tag: str | None = None) -> list[AgentSummary]:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.list_agents(s, TENANT, tag=tag)
    return [
        AgentSummary(id=str(r["id"]), name=r["name"], current_version=r["current_version"],
                     tags=r.get("tags") or [])
        for r in rows
    ]


@router.get("/agent-tags")
async def list_agent_tags() -> list[str]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_agent_tags(s, TENANT)


@router.put("/agents/{agent_id}/tags")
async def set_agent_tags(agent_id: str, req: TagsRequest) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.set_agent_tags(s, agent_id, req.tags)
        await s.commit()
    return {"ok": True, "tags": sorted({t.strip() for t in req.tags if t.strip()})}


@router.post("/agents/delete")
async def delete_agents(req: IdsRequest) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_agents(s, TENANT, req.ids)
        await s.commit()
    return {"deleted": n}


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


# ───────────────────────── activity / logs (runs + steps) ─────────────────────────
@router.get("/runs")
async def list_runs() -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_runs(s, TENANT)


@router.get("/runs/{run_id}/steps")
async def get_run_steps(run_id: str) -> dict:
    """A run plus its full, ordered step log — every tracked bit."""
    sm = get_sessionmaker()
    async with sm() as s:
        run = await repo.get_run(s, run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        steps = await repo.get_run_steps(s, run_id)
    return {"run": run, "steps": steps}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_runs(s, TENANT, [run_id])
        await s.commit()
    return {"deleted": n}


@router.post("/runs/delete")
async def delete_runs(req: IdsRequest) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_runs(s, TENANT, req.ids)
        await s.commit()
    return {"deleted": n}


# ───────────────────────── learning (feedback → reflect → lessons) ─────────────────────────
@router.post("/runs/{run_id}/feedback")
async def run_feedback(run_id: str, req: FeedbackRequest) -> dict:
    """Rate a run. A 👎 on an auto-improving agent triggers reflection immediately."""
    sm = get_sessionmaker()
    async with sm() as s:
        run = await repo.set_run_feedback(s, run_id, req.reward, req.note)
        if run is None:
            raise HTTPException(404, "run not found")
        agent_id = str(run["agent_id"]) if run.get("agent_id") else None
        spec = await repo.get_spec(s, agent_id) if agent_id else None
        await s.commit()
    learned = None
    if req.reward < 0 and agent_id and spec and spec.get("auto_improve"):
        try:
            learned = await learning.reflect(agent_id, run_id, TENANT)
        except Exception as exc:  # feedback must always succeed even if reflection fails
            learned = {"error": str(exc)}
    return {"ok": True, "learned": learned}


@router.post("/agents/{agent_id}/reflect")
async def agent_reflect(agent_id: str, req: ReflectRequest) -> dict:
    """Reflect on a run now and learn a lesson (manual self-improvement)."""
    try:
        return await learning.reflect(agent_id, req.run_id, TENANT)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/agents/{agent_id}/lessons")
async def agent_lessons(agent_id: str) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_lessons(s, agent_id)


# ───────────────────────── Faust (floating admin bot) ─────────────────────────
async def _faust_stream(req: AskRequest) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    agent_id = await faust.get_or_create_faust(TENANT)
    async with sm() as s:
        run_id = await repo.create_run(
            s, TENANT, "ask", {"message": req.message}, agent_id=agent_id
        )
        await s.commit()
    yield events.ev("run", run_id=run_id)
    answer: str | None = None
    try:
        async for event in faust.run_faust(req.message, TENANT, run_id, history=req.history):
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


@router.post("/faust/ask")
async def faust_ask(req: AskRequest):
    return EventSourceResponse(_faust_stream(req))
