"""Edge HTTP API: REST for upload / build / ask / self-mod, SSE for streaming.

Every handler resolves a request :class:`~veldra_app.auth.Context` (tenant + user +
role) via the ``get_context`` dependency — the keystone that replaced the old global
single-tenant constant. Reads accept any authenticated role; mutations require at
least ``member`` (a ``viewer`` is read-only). When ``VELDRA_AUTH_ENABLED=false`` the
context resolves to the default workspace as a system admin (CLI / evals / local).

SSE is emitted directly from these handlers; Redis fan-out activates only when a
second process exists.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse
from veldra_spec import AgentSpec

from veldra_app import events, faust, learning, repo
from veldra_app.auth import Context, get_context, require_role
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
    LessonRequest,
    ManualAgentRequest,
    ReflectRequest,
    SelfModApplyRequest,
    SelfModProposeRequest,
    SkillRequest,
    SkillUpdateRequest,
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

# Reads accept any authenticated role; mutations require >= member.
Ctx = Annotated[Context, Depends(get_context)]
Member = Annotated[Context, Depends(require_role("member"))]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
async def get_config(ctx: Ctx) -> dict:
    """Safe, secret-free view of the active configuration (for the Settings panel)."""
    import os

    from veldra_app.config import get_settings

    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "orchestrator_model": s.orchestrator_model,
        "worker_model": s.worker_model,
        "ollama_model": s.ollama_model,
        "embed_provider": s.embed_provider,
        "embed_dim": s.embed_dim,
        "vector_store": os.getenv("VELDRA_VECTOR_STORE", "pgvector"),
        "env": s.env,
        "role": ctx.role,
    }


@router.get("/tools")
async def list_tools(ctx: Ctx) -> list[dict]:
    """The catalog of tools (built-in + enabled plugins) agents can be granted."""
    from veldra_app.tools_registry import get_catalog

    return await get_catalog(ctx.tenant_id)


@router.get("/analytics")
async def get_analytics(ctx: Ctx) -> dict:
    """Rollups over the durable runs log: success rate, cost/tokens, latency,
    per-agent stats, reward distribution, error feed, and tuning suggestions."""
    from veldra_app import analytics

    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.analytics_rows(s, ctx.tenant_id)
    return analytics.compute(rows)


# ───────────────────────── knowledge bases ─────────────────────────
def _ingest_response(result) -> UploadResponse:
    return UploadResponse(
        document_id=result.document_id, kb_id=result.kb_id, filename=result.filename,
        num_pages=result.num_pages, num_chunks=result.num_chunks,
    )


@router.get("/kb")
async def list_kbs(ctx: Ctx) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_kbs(s, ctx.tenant_id)


@router.post("/kb")
async def create_kb(req: KbCreateRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    cfg = req.model_dump(exclude={"name"}, exclude_none=True)
    async with sm() as s:
        kb_id = await repo.create_kb(s, ctx.tenant_id, req.name, **cfg)
        await s.commit()
        kb = await repo.get_kb(s, kb_id, ctx.tenant_id)
    return kb or {"id": kb_id, "name": req.name}


@router.get("/kb/{kb_id}")
async def get_kb(kb_id: str, ctx: Ctx) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        kb = await repo.get_kb(s, kb_id, ctx.tenant_id)
    if kb is None:
        raise HTTPException(404, "knowledge base not found")
    return kb


@router.patch("/kb/{kb_id}")
@router.put("/kb/{kb_id}")
async def update_kb(kb_id: str, req: KbUpdateRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        if await repo.get_kb(s, kb_id, ctx.tenant_id) is None:
            raise HTTPException(404, "knowledge base not found")
        await repo.update_kb(s, kb_id, tenant_id=ctx.tenant_id, **req.model_dump(exclude_none=True))
        await s.commit()
        return await repo.get_kb(s, kb_id, ctx.tenant_id)


@router.delete("/kb/{kb_id}")
async def delete_kb(kb_id: str, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_kb(s, kb_id, ctx.tenant_id)
        await s.commit()
    return {"deleted": kb_id}


@router.get("/kb/{kb_id}/documents")
async def list_documents(kb_id: str, ctx: Ctx) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_documents(s, kb_id, ctx.tenant_id)


@router.post("/kb/{kb_id}/upload", response_model=UploadResponse)
async def upload_to_kb(kb_id: str, ctx: Member, file: UploadFile = File(...)) -> UploadResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    result = await ingest_document(
        data, file.filename or "document",
        file.content_type or "application/octet-stream", ctx.tenant_id, kb_id=kb_id,
    )
    return _ingest_response(result)


@router.post("/kb/{kb_id}/ingest-url", response_model=UploadResponse)
async def ingest_from_url(kb_id: str, req: UrlIngestRequest, ctx: Member) -> UploadResponse:
    """Fetch a web page and index it into the KB (web page index)."""
    try:
        result = await ingest_url(req.url, ctx.tenant_id, kb_id=kb_id)
    except Exception as exc:
        raise HTTPException(400, f"could not ingest URL: {exc}") from exc
    return _ingest_response(result)


@router.get("/kb/{kb_id}/documents/{doc_id}")
async def get_document(kb_id: str, doc_id: str, ctx: Ctx) -> dict:
    """Document detail + editable text + the page-index tree."""
    sm = get_sessionmaker()
    async with sm() as s:
        doc = await repo.get_document(s, doc_id, ctx.tenant_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        text = await repo.get_document_text(s, doc_id)
        page_index = await repo.get_page_index(s, doc_id)
    return {"document": doc, "text": text, "page_index": page_index}


@router.put("/kb/{kb_id}/documents/{doc_id}", response_model=UploadResponse)
async def edit_document(
    kb_id: str, doc_id: str, req: DocEditRequest, ctx: Member
) -> UploadResponse:
    """Replace a saved document's content with edited text and re-embed it."""
    try:
        result = await reingest_text(doc_id, req.text, ctx.tenant_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _ingest_response(result)


@router.post("/kb/{kb_id}/documents/delete")
async def delete_documents(kb_id: str, req: IdsRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_documents(s, kb_id, req.ids, tenant_id=ctx.tenant_id)
        await s.commit()
    return {"deleted": n}


@router.delete("/kb/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_document(s, doc_id, ctx.tenant_id)
        await s.commit()
    return {"deleted": doc_id}


@router.post("/kb/upload", response_model=UploadResponse)
async def upload(ctx: Member, file: UploadFile = File(...)) -> UploadResponse:
    """Upload to the default KB (kept for convenience / the CLI)."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    result = await ingest_document(
        data, file.filename or "document",
        file.content_type or "application/octet-stream", ctx.tenant_id,
    )
    return _ingest_response(result)


# ───────────────────────── skills (markdown playbooks) ─────────────────────────
@router.get("/skills")
async def list_skills(ctx: Ctx) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_skills(s, ctx.tenant_id)


@router.post("/skills")
async def create_skill(req: SkillRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        sid = await repo.create_skill(s, ctx.tenant_id, req.name, req.description, req.content)
        await s.commit()
        return await repo.get_skill(s, sid)


@router.put("/skills/{skill_id}")
@router.patch("/skills/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        if await repo.get_skill(s, skill_id) is None:
            raise HTTPException(404, "skill not found")
        await repo.update_skill(s, skill_id, **req.model_dump(exclude_none=True))
        await s.commit()
        return await repo.get_skill(s, skill_id)


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_skill(s, skill_id)
        await s.commit()
    return {"deleted": skill_id}


async def _ensure_finished(run_id: str) -> None:
    """Finalize a run still marked 'running' — e.g. the client disconnected mid-stream
    (raises GeneratorExit, which the `except Exception` blocks don't catch). Idempotent:
    a no-op once the normal/error path has already finished the run."""
    sm = get_sessionmaker()
    async with sm() as s:
        run = await repo.get_run(s, run_id)
        if run and run.get("status") == "running":
            await repo.finish_run(s, run_id, "error", error="interrupted (client disconnected)")
            await s.commit()


# ───────────────────────── build (NL -> agent) ─────────────────────────
async def _build_stream(req: BuildRequest, tenant: str) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    if req.idempotency_key:
        async with sm() as s:
            prior = await repo.get_run_by_idem(s, tenant, req.idempotency_key)
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
            s, tenant, "build", {"request": req.request}, idempotency_key=req.idempotency_key
        )
        await s.commit()

    result: dict | None = None
    try:
        async for event in build_agent(req.request, tenant, run_id):
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
    finally:
        await _ensure_finished(run_id)


@router.post("/agents/build")
async def agents_build(req: BuildRequest, ctx: Member):
    return EventSourceResponse(_build_stream(req, ctx.tenant_id), ping=15)


# ───────────────────────── ask (run an agent) ─────────────────────────
async def _ask_stream(agent_id: str, req: AskRequest, tenant: str) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        agent = await repo.get_agent(s, agent_id)
        spec_dict = await repo.get_spec(s, agent_id) if agent else None
    if spec_dict is None or (agent and str(agent.get("tenant_id")) != str(tenant)):
        yield events.error("Agent not found.")
        return

    spec = AgentSpec.model_validate(spec_dict)
    async with sm() as s:
        run_id = await repo.create_run(
            s, tenant, "ask", {"message": req.message},
            agent_id=agent_id, agent_version=agent["current_version"],
        )
        await s.commit()
        # Inject episodic memory + granted skills into the agent's instructions.
        lessons = await repo.list_lessons(s, agent_id, limit=10)
        skills = await repo.get_skills_by_names(s, tenant, spec.skills)
    extra = ""
    if skills:
        blocks = "\n\n".join(f"### Skill: {sk['name']}\n{sk['content']}" for sk in skills)
        extra += f"\n\n## Skills (follow these playbooks)\n{blocks}"
    if lessons:
        extra += learning.lessons_block(lessons)
    if extra:
        spec = spec.model_copy(update={"system_prompt": spec.system_prompt + extra})

    # Tell the client which run this is, so it can attach 👍/👎 feedback.
    yield events.ev("run", run_id=run_id)
    answer: str | None = None
    usage: dict | None = None
    try:
        async for event in execute(
            spec, req.message, tenant_id=tenant, run_id=run_id, history=req.history,
            approved_tools=req.approved_tools,
        ):
            if event["event"] == "done":
                answer = json.loads(event["data"]).get("answer")
            elif event["event"] == "usage":
                usage = json.loads(event["data"])
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done", result={"answer": answer, "usage": usage})
            await s.commit()
    except Exception as exc:
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()
    finally:
        await _ensure_finished(run_id)


@router.post("/agents/{agent_id}/ask")
async def agents_ask(agent_id: str, req: AskRequest, ctx: Member):
    return EventSourceResponse(_ask_stream(agent_id, req, ctx.tenant_id), ping=15)


# ───────────────────────── routing (auto-select an agent) ─────────────────────────
@router.post("/agents/route")
async def route_agent(req: AskRequest, ctx: Member) -> dict:
    """Pick the best existing agent for a free-text message, or {action: create} when
    none fits — the backend half of the smart composer (type → route or build)."""
    from veldra_app.orchestrator.route import route_message

    sm = get_sessionmaker()
    async with sm() as s:
        roster = await repo.list_agents(s, ctx.tenant_id)
    return await route_message(req.message, roster)


# ───────────────────────── self-modification ─────────────────────────
async def _selfmod_stream(
    agent_id: str, req: SelfModProposeRequest, tenant: str
) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        run_id = await repo.create_run(
            s, tenant, "selfmod", {"instruction": req.instruction}, agent_id=agent_id
        )
        await s.commit()
    try:
        async for event in selfmod.propose(agent_id, req.instruction, tenant):
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done")
            await s.commit()
    except Exception as exc:
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()
    finally:
        await _ensure_finished(run_id)


@router.post("/agents/{agent_id}/selfmod/propose")
async def selfmod_propose(agent_id: str, req: SelfModProposeRequest, ctx: Member):
    return EventSourceResponse(_selfmod_stream(agent_id, req, ctx.tenant_id), ping=15)


@router.post("/agents/{agent_id}/selfmod/apply")
async def selfmod_apply(agent_id: str, req: SelfModApplyRequest, ctx: Member) -> dict:
    try:
        return await selfmod.apply(agent_id, req.spec, ctx.tenant_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/agents/{agent_id}/workflow")
async def save_workflow(agent_id: str, req: WorkflowSaveRequest, ctx: Member) -> dict:
    """Persist a workflow graph edited in the visual builder (new spec version)."""
    try:
        return await selfmod.set_workflow(agent_id, req.graph, ctx.tenant_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ───────────────────────── read endpoints ─────────────────────────
@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(ctx: Ctx, tag: str | None = None) -> list[AgentSummary]:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.list_agents(s, ctx.tenant_id, tag=tag)
    return [AgentSummary(**{**r, "id": str(r["id"]), "tags": r.get("tags") or []}) for r in rows]


@router.post("/agents")
async def create_agent_manual(req: ManualAgentRequest, ctx: Member) -> dict:
    """Create an agent from a full spec the user authored by hand (the 'Manual' tab of
    the create flow). Validates the schema + that every tool exists, then persists v1."""
    from veldra_app.tools_registry import get_catalog

    try:
        spec = AgentSpec.model_validate(req.spec)
    except Exception as exc:
        raise HTTPException(400, f"Invalid agent spec: {exc}") from exc
    allowed = {t["name"] for t in await get_catalog(ctx.tenant_id)}
    bad = [t for t in spec.tool_keys() if t not in allowed]
    if bad:
        raise HTTPException(400, f"Unknown tool(s): {', '.join(sorted(bad))}")
    sm = get_sessionmaker()
    async with sm() as s:
        agent_id, version = await repo.upsert_agent_spec(
            s, ctx.tenant_id, spec.name, spec.model_dump(mode="json"), note="manual create"
        )
        await s.commit()
    return {"agent_id": agent_id, "version": version, "spec": spec.model_dump(mode="json")}


@router.get("/agent-tags")
async def list_agent_tags(ctx: Ctx) -> list[str]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_agent_tags(s, ctx.tenant_id)


@router.put("/agents/{agent_id}/tags")
async def set_agent_tags(agent_id: str, req: TagsRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.set_agent_tags(s, agent_id, req.tags)
        await s.commit()
    return {"ok": True, "tags": sorted({t.strip() for t in req.tags if t.strip()})}


@router.post("/agents/delete")
async def delete_agents(req: IdsRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_agents(s, ctx.tenant_id, req.ids)
        await s.commit()
    return {"deleted": n}


@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent(agent_id: str, ctx: Ctx) -> AgentDetail:
    sm = get_sessionmaker()
    async with sm() as s:
        agent = await repo.get_agent(s, agent_id)
        spec = await repo.get_spec(s, agent_id) if agent else None
    if not agent or spec is None or str(agent.get("tenant_id")) != str(ctx.tenant_id):
        raise HTTPException(404, "agent not found")
    return AgentDetail(
        id=str(agent["id"]), name=agent["name"],
        current_version=agent["current_version"], spec=spec,
    )


# ───────────────────────── activity / logs (runs + steps) ─────────────────────────
@router.get("/runs")
async def list_runs(ctx: Ctx, limit: int = 60, offset: int = 0) -> list[dict]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_runs(s, ctx.tenant_id, limit=limit, offset=offset)


@router.get("/runs/{run_id}/steps")
async def get_run_steps(run_id: str, ctx: Ctx) -> dict:
    """A run plus its full, ordered step log — every tracked bit."""
    sm = get_sessionmaker()
    async with sm() as s:
        run = await repo.get_run(s, run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        steps = await repo.get_run_steps(s, run_id)
    return {"run": run, "steps": steps}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_runs(s, ctx.tenant_id, [run_id])
        await s.commit()
    return {"deleted": n}


@router.post("/runs/delete")
async def delete_runs(req: IdsRequest, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        n = await repo.delete_runs(s, ctx.tenant_id, req.ids)
        await s.commit()
    return {"deleted": n}


# ───────────────────────── learning (feedback → reflect → lessons) ─────────────────────────
@router.post("/runs/{run_id}/feedback")
async def run_feedback(run_id: str, req: FeedbackRequest, ctx: Member) -> dict:
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
            learned = await learning.reflect(agent_id, run_id, ctx.tenant_id)
        except Exception as exc:  # feedback must always succeed even if reflection fails
            learned = {"error": str(exc)}
    return {"ok": True, "learned": learned}


@router.post("/agents/{agent_id}/reflect")
async def agent_reflect(agent_id: str, req: ReflectRequest, ctx: Member) -> dict:
    """Reflect on a run now and learn a lesson (manual self-improvement)."""
    try:
        return await learning.reflect(agent_id, req.run_id, ctx.tenant_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/agents/{agent_id}/lessons")
async def agent_lessons(agent_id: str, ctx: Ctx) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as s:
        return await repo.list_lessons(s, agent_id)


@router.post("/agents/{agent_id}/lessons")
async def teach_lesson(agent_id: str, req: LessonRequest, ctx: Member) -> dict:
    """Teach an agent something directly — it remembers it (episodic memory),
    injected into its instructions on every future run. The hands-on 'grow' lever."""
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, "lesson content is required")
    sm = get_sessionmaker()
    async with sm() as s:
        if not await repo.get_agent(s, agent_id):
            raise HTTPException(404, "Agent not found.")
        lid = await repo.add_lesson(s, ctx.tenant_id, agent_id, content[:1000], source_run_id=None)
        await s.commit()
    return {"id": lid}


@router.delete("/agents/{agent_id}/lessons/{lesson_id}")
async def forget_lesson(agent_id: str, lesson_id: str, ctx: Member) -> dict:
    sm = get_sessionmaker()
    async with sm() as s:
        await repo.delete_lesson(s, agent_id, lesson_id)
        await s.commit()
    return {"ok": True}


# ───────────────────────── Faust (floating admin bot) ─────────────────────────
async def _faust_stream(req: AskRequest, tenant: str) -> AsyncIterator[dict]:
    sm = get_sessionmaker()
    agent_id = await faust.get_or_create_faust(tenant)
    async with sm() as s:
        run_id = await repo.create_run(
            s, tenant, "ask", {"message": req.message}, agent_id=agent_id
        )
        await s.commit()
    yield events.ev("run", run_id=run_id)
    answer: str | None = None
    usage: dict | None = None
    try:
        async for event in faust.run_faust(req.message, tenant, run_id, history=req.history):
            if event["event"] == "done":
                answer = json.loads(event["data"]).get("answer")
            elif event["event"] == "usage":
                usage = json.loads(event["data"])
            yield event
        async with sm() as s:
            await repo.finish_run(s, run_id, "done", result={"answer": answer, "usage": usage})
            await s.commit()
    except Exception as exc:
        yield events.error(str(exc))
        async with sm() as s:
            await repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()
    finally:
        await _ensure_finished(run_id)


@router.post("/faust/ask")
async def faust_ask(req: AskRequest, ctx: Annotated[Context, Depends(require_role("admin"))]):
    return EventSourceResponse(_faust_stream(req, ctx.tenant_id), ping=15)
