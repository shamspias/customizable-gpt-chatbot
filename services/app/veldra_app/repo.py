"""Async data access over the SQLAlchemy ORM models (`veldra_app.models`).

Queries use the 2.0 expression language against the mapped classes — no raw SQL.
JSONB columns take/return plain dicts (the engine's json_serializer handles
datetimes); the pgvector `embedding` column takes/returns a list[float] directly.
Read helpers return plain dicts (same shape the edge/runtime layers expect);
callers own the transaction (commit on the session).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from veldra_app.models import (
    Agent,
    Audit,
    Chunk,
    Document,
    KnowledgeBase,
    Lesson,
    PageIndex,
    Run,
    RunStep,
    SpecVersion,
)


def is_uuid(value: str | None) -> bool:
    """Guard so an invalid path param (e.g. 'None') yields a 404, not a DB DataError."""
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


# ───────────────────────── knowledge bases / documents ─────────────────────────
async def get_or_create_kb(session: AsyncSession, tenant_id: str, name: str = "default") -> str:
    kb_id = await session.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.name == name
        )
    )
    if kb_id:
        return str(kb_id)
    return str(
        await session.scalar(
            insert(KnowledgeBase).values(tenant_id=tenant_id, name=name).returning(KnowledgeBase.id)
        )
    )


# Columns describing a KB's retrieval behaviour (returned to the UI + retriever).
_KB_COLS = (
    KnowledgeBase.id, KnowledgeBase.name, KnowledgeBase.description,
    KnowledgeBase.retrieval_mode, KnowledgeBase.embedding_model,
    KnowledgeBase.rerank_model, KnowledgeBase.page_index_enabled,
    KnowledgeBase.created_at,
)


async def create_kb(
    session: AsyncSession, tenant_id: str, name: str, **config: Any
) -> str:
    allowed = {
        k: v for k, v in config.items()
        if k in {"description", "retrieval_mode", "embedding_model",
                 "rerank_model", "page_index_enabled"} and v is not None
    }
    return str(
        await session.scalar(
            insert(KnowledgeBase)
            .values(tenant_id=tenant_id, name=name, **allowed)
            .returning(KnowledgeBase.id)
        )
    )


async def get_kb(session: AsyncSession, kb_id: str) -> dict | None:
    if not is_uuid(kb_id):
        return None
    res = await session.execute(select(*_KB_COLS).where(KnowledgeBase.id == kb_id))
    row = res.mappings().first()
    return dict(row) if row else None


async def update_kb(session: AsyncSession, kb_id: str, **fields: Any) -> None:
    if not is_uuid(kb_id):
        return
    allowed = {
        k: v for k, v in fields.items()
        if k in {"name", "description", "retrieval_mode", "embedding_model",
                 "rerank_model", "page_index_enabled"} and v is not None
    }
    if allowed:
        await session.execute(
            update(KnowledgeBase).where(KnowledgeBase.id == kb_id).values(**allowed)
        )


async def list_kbs(session: AsyncSession, tenant_id: str) -> list[dict]:
    doc_count = (
        select(func.count(Document.id))
        .where(Document.kb_id == KnowledgeBase.id)
        .correlate(KnowledgeBase)
        .scalar_subquery()
    )
    res = await session.execute(
        select(*_KB_COLS, doc_count.label("document_count"))
        .where(KnowledgeBase.tenant_id == tenant_id)
        .order_by(KnowledgeBase.created_at)
    )
    return [dict(r) for r in res.mappings()]


async def list_documents(session: AsyncSession, kb_id: str) -> list[dict]:
    if not is_uuid(kb_id):
        return []
    chunk_count = (
        select(func.count(Chunk.id))
        .where(Chunk.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    res = await session.execute(
        select(
            Document.id, Document.filename, Document.content_type, Document.num_pages,
            Document.status, Document.created_at, chunk_count.label("chunk_count"),
        )
        .where(Document.kb_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    return [dict(r) for r in res.mappings()]


async def delete_document(session: AsyncSession, doc_id: str) -> None:
    if not is_uuid(doc_id):
        return
    await session.execute(delete(Document).where(Document.id == doc_id))


async def delete_kb(session: AsyncSession, kb_id: str) -> None:
    if not is_uuid(kb_id):
        return
    await session.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))


async def create_document(
    session: AsyncSession,
    kb_id: str,
    tenant_id: str,
    filename: str,
    content_type: str,
    s3_key: str,
) -> str:
    return str(
        await session.scalar(
            insert(Document)
            .values(
                kb_id=kb_id, tenant_id=tenant_id, filename=filename,
                content_type=content_type, s3_key=s3_key,
            )
            .returning(Document.id)
        )
    )


async def set_document_status(
    session: AsyncSession,
    doc_id: str,
    status: str,
    num_pages: int | None = None,
    error: str | None = None,
) -> None:
    values: dict[str, Any] = {"status": status, "error": error}
    if num_pages is not None:
        values["num_pages"] = num_pages
    await session.execute(update(Document).where(Document.id == doc_id).values(**values))


async def insert_page_index(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if rows:
        await session.execute(insert(PageIndex), rows)


async def insert_chunks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Each row: id, document_id, kb_id, tenant_id, ordinal, content, page_number,
    section_path, char_start, char_end, token_count, embedding (list[float])."""
    if rows:
        await session.execute(insert(Chunk), rows)


def _chunk_citation_cols() -> list:
    return [
        Chunk.id, Chunk.content, Chunk.page_number, Chunk.section_path,
        Chunk.char_start, Chunk.char_end, Document.filename,
    ]


async def vector_search(
    session: AsyncSession, tenant_id: str, kb_ids: list[str], emb: list[float], n: int
) -> list[dict]:
    distance = Chunk.embedding.cosine_distance(emb).label("distance")
    res = await session.execute(
        select(*_chunk_citation_cols(), distance)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.tenant_id == tenant_id, Chunk.kb_id.in_(kb_ids))
        .order_by(distance)
        .limit(n)
    )
    return [dict(r) for r in res.mappings()]


async def lexical_search(
    session: AsyncSession, tenant_id: str, kb_ids: list[str], query: str, n: int
) -> list[dict]:
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(Chunk.tsv, tsquery).label("rank")
    res = await session.execute(
        select(*_chunk_citation_cols(), rank)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.tenant_id == tenant_id,
            Chunk.kb_id.in_(kb_ids),
            Chunk.tsv.op("@@")(tsquery),
        )
        .order_by(rank.desc())
        .limit(n)
    )
    return [dict(r) for r in res.mappings()]


async def get_chunks_by_ids(session: AsyncSession, ids: list[str]) -> list[dict]:
    """Fetch chunk content + citation metadata for ids (used after a vector-store query)."""
    if not ids:
        return []
    res = await session.execute(
        select(*_chunk_citation_cols())
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(ids))
    )
    return [dict(r) for r in res.mappings()]


# ───────────────────────── agents / specs (versioned) ─────────────────────────
async def get_agent_by_name(session: AsyncSession, tenant_id: str, name: str) -> dict | None:
    res = await session.execute(
        select(Agent.id, Agent.name, Agent.current_version).where(
            Agent.tenant_id == tenant_id, Agent.name == name
        )
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_agent(session: AsyncSession, agent_id: str) -> dict | None:
    if not is_uuid(agent_id):
        return None
    res = await session.execute(
        select(Agent.id, Agent.tenant_id, Agent.name, Agent.current_version, Agent.tags).where(
            Agent.id == agent_id
        )
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def insert_spec_version(
    session: AsyncSession, agent_id: str, spec: dict, note: str | None = None
) -> int:
    version = await session.scalar(
        select(func.coalesce(func.max(SpecVersion.version), 0) + 1).where(
            SpecVersion.agent_id == agent_id
        )
    )
    await session.execute(
        insert(SpecVersion).values(agent_id=agent_id, version=version, spec=spec, note=note)
    )
    return int(version)


async def set_current_version(session: AsyncSession, agent_id: str, version: int) -> None:
    await session.execute(
        update(Agent).where(Agent.id == agent_id).values(current_version=version)
    )


async def rename_agent(session: AsyncSession, agent_id: str, new_name: str) -> None:
    """Rename an agent: update the display name AND the current spec's name (new version)."""
    if not is_uuid(agent_id):
        return
    new_name = new_name.strip()
    spec = await get_spec(session, agent_id)
    if spec is not None and spec.get("name") != new_name:
        version = await insert_spec_version(
            session, agent_id, {**spec, "name": new_name}, note="rename"
        )
        await set_current_version(session, agent_id, version)
    await session.execute(update(Agent).where(Agent.id == agent_id).values(name=new_name))


async def upsert_agent_spec(
    session: AsyncSession, tenant_id: str, name: str, spec: dict, note: str | None = None
) -> tuple[str, int]:
    """Create a fresh agent (version 1) or append a new version to an existing one."""
    existing = await get_agent_by_name(session, tenant_id, name)
    if existing is None:
        agent_id = str(
            await session.scalar(
                insert(Agent)
                .values(tenant_id=tenant_id, name=name, current_version=1)
                .returning(Agent.id)
            )
        )
        await insert_spec_version(session, agent_id, spec, note)
        return agent_id, 1
    agent_id = str(existing["id"])
    version = await insert_spec_version(session, agent_id, spec, note)
    await set_current_version(session, agent_id, version)
    return agent_id, version


async def get_spec(
    session: AsyncSession, agent_id: str, version: int | None = None
) -> dict | None:
    if not is_uuid(agent_id):
        return None
    if version is None:
        stmt = (
            select(SpecVersion.spec)
            .join(
                Agent,
                (Agent.id == SpecVersion.agent_id) & (Agent.current_version == SpecVersion.version),
            )
            .where(SpecVersion.agent_id == agent_id)
        )
    else:
        stmt = select(SpecVersion.spec).where(
            SpecVersion.agent_id == agent_id, SpecVersion.version == version
        )
    spec = await session.scalar(stmt)
    if spec is None:
        return None
    return spec if isinstance(spec, dict) else dict(spec)


async def list_agents(
    session: AsyncSession, tenant_id: str, tag: str | None = None
) -> list[dict]:
    stmt = (
        select(Agent.id, Agent.name, Agent.current_version, Agent.tags, Agent.created_at)
        .where(Agent.tenant_id == tenant_id)
        .order_by(Agent.created_at.desc())
    )
    if tag:
        stmt = stmt.where(Agent.tags.contains([tag]))
    res = await session.execute(stmt)
    return [dict(r) for r in res.mappings()]


async def list_agent_tags(session: AsyncSession, tenant_id: str) -> list[str]:
    """All distinct tags in use (for the filter UI)."""
    res = await session.execute(select(Agent.tags).where(Agent.tenant_id == tenant_id))
    seen: dict[str, None] = {}
    for (tags,) in res.all():
        for t in tags or []:
            seen[t] = None
    return sorted(seen)


async def set_agent_tags(session: AsyncSession, agent_id: str, tags: list[str]) -> None:
    if not is_uuid(agent_id):
        return
    clean = sorted({str(t).strip() for t in tags if str(t).strip()})
    await session.execute(update(Agent).where(Agent.id == agent_id).values(tags=clean))


async def delete_agents(session: AsyncSession, tenant_id: str, ids: list[str]) -> int:
    """Bulk-delete agents, tenant-scoped. agent_specs + lessons cascade via FK, but
    runs.agent_id has no cascade, so we drop dependent runs (and their steps) first."""
    valid = [i for i in ids if is_uuid(i)]
    if not valid:
        return 0
    run_ids = (
        select(Run.id).where(Run.tenant_id == tenant_id, Run.agent_id.in_(valid)).scalar_subquery()
    )
    await session.execute(delete(RunStep).where(RunStep.run_id.in_(run_ids)))
    await session.execute(delete(Run).where(Run.tenant_id == tenant_id, Run.agent_id.in_(valid)))
    res = await session.execute(
        delete(Agent).where(Agent.tenant_id == tenant_id, Agent.id.in_(valid))
    )
    return res.rowcount or 0


async def delete_runs(session: AsyncSession, tenant_id: str, ids: list[str]) -> int:
    """Bulk-delete activity-log runs (run_steps cascade via FK); tenant-scoped."""
    valid = [i for i in ids if is_uuid(i)]
    if not valid:
        return 0
    res = await session.execute(
        delete(Run).where(Run.tenant_id == tenant_id, Run.id.in_(valid))
    )
    return res.rowcount or 0


async def delete_all_runs(
    session: AsyncSession, tenant_id: str, kind: str | None = None
) -> int:
    """Delete ALL runs for a tenant in one statement (optionally a single kind) — no
    row cap. Used by Faust's 'clear logs' so it never silently leaves runs behind."""
    stmt = delete(Run).where(Run.tenant_id == tenant_id)
    if kind:
        stmt = stmt.where(Run.kind == kind)
    res = await session.execute(stmt)
    return res.rowcount or 0


async def delete_documents(session: AsyncSession, kb_id: str, ids: list[str]) -> int:
    """Bulk-delete documents in a KB (chunks/page_index cascade via FK)."""
    valid = [i for i in ids if is_uuid(i)]
    if not valid or not is_uuid(kb_id):
        return 0
    res = await session.execute(
        delete(Document).where(Document.kb_id == kb_id, Document.id.in_(valid))
    )
    return res.rowcount or 0


# ───────────────────────── runs / steps / audit ─────────────────────────
async def get_run_by_idem(session: AsyncSession, tenant_id: str, key: str) -> dict | None:
    res = await session.execute(
        select(Run.id, Run.status, Run.result, Run.agent_id, Run.agent_version).where(
            Run.tenant_id == tenant_id, Run.idempotency_key == key
        )
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def create_run(
    session: AsyncSession,
    tenant_id: str,
    kind: str,
    input: dict,
    idempotency_key: str | None = None,
    agent_id: str | None = None,
    agent_version: int | None = None,
) -> str:
    return str(
        await session.scalar(
            insert(Run)
            .values(
                tenant_id=tenant_id, kind=kind, input=input,
                idempotency_key=idempotency_key, agent_id=agent_id, agent_version=agent_version,
            )
            .returning(Run.id)
        )
    )


async def finish_run(
    session: AsyncSession,
    run_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(status=status, result=result, error=error, finished_at=func.now())
    )


async def insert_run_step(
    session: AsyncSession, run_id: str, ordinal: int, type: str, name: str | None, payload: dict
) -> None:
    await session.execute(
        insert(RunStep).values(
            run_id=run_id, ordinal=ordinal, type=type, name=name, payload=payload
        )
    )


async def insert_audit(
    session: AsyncSession,
    tenant_id: str,
    actor: str,
    action: str,
    target_type: str | None,
    target_id: str | None,
    detail: dict,
) -> None:
    await session.execute(
        insert(Audit).values(
            tenant_id=tenant_id, actor=actor, action=action,
            target_type=target_type, target_id=target_id, detail=detail,
        )
    )


# ───────────────────────── observability (runs + steps) ─────────────────────────
async def list_runs(session: AsyncSession, tenant_id: str, limit: int = 60) -> list[dict]:
    """Recent runs (build/ask/selfmod) with the agent name, newest first."""
    res = await session.execute(
        select(
            Run.id, Run.kind, Run.status, Run.agent_id, Run.agent_version,
            Run.error, Run.created_at, Run.finished_at, Agent.name.label("agent_name"),
        )
        .join(Agent, Agent.id == Run.agent_id, isouter=True)
        .where(Run.tenant_id == tenant_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    return [dict(r) for r in res.mappings()]


async def get_run(session: AsyncSession, run_id: str) -> dict | None:
    if not is_uuid(run_id):
        return None
    res = await session.execute(
        select(
            Run.id, Run.kind, Run.status, Run.agent_id, Run.agent_version,
            Run.input, Run.result, Run.error, Run.created_at, Run.finished_at,
        ).where(Run.id == run_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_run_steps(session: AsyncSession, run_id: str) -> list[dict]:
    """The full append-only step log for a run — every tracked bit."""
    if not is_uuid(run_id):
        return []
    res = await session.execute(
        select(RunStep.ordinal, RunStep.type, RunStep.name, RunStep.payload, RunStep.created_at)
        .where(RunStep.run_id == run_id)
        .order_by(RunStep.ordinal)
    )
    return [dict(r) for r in res.mappings()]


async def set_run_feedback(
    session: AsyncSession, run_id: str, reward: float | None, feedback: str | None
) -> dict | None:
    """Attach a reward (-1..1) + optional note to a run; returns the run (with agent_id)."""
    if not is_uuid(run_id):
        return None
    await session.execute(
        update(Run).where(Run.id == run_id).values(reward=reward, feedback=feedback)
    )
    return await get_run(session, run_id)


# ───────────────────────── episodic memory (lessons) ─────────────────────────
LESSON_CAP = 50  # keep an agent's episodic memory bounded (most recent kept)


async def add_lesson(
    session: AsyncSession, tenant_id: str, agent_id: str, content: str,
    source_run_id: str | None = None,
) -> str:
    lesson_id = str(
        await session.scalar(
            insert(Lesson)
            .values(tenant_id=tenant_id, agent_id=agent_id, content=content,
                    source_run_id=source_run_id)
            .returning(Lesson.id)
        )
    )
    # Prune to the most recent LESSON_CAP so memory + prompt injection stay bounded.
    keep = select(Lesson.id).where(Lesson.agent_id == agent_id).order_by(
        Lesson.created_at.desc()
    ).limit(LESSON_CAP).scalar_subquery()
    await session.execute(
        delete(Lesson).where(Lesson.agent_id == agent_id, Lesson.id.not_in(keep))
    )
    return lesson_id


async def list_lessons(session: AsyncSession, agent_id: str, limit: int = 20) -> list[dict]:
    if not is_uuid(agent_id):
        return []
    res = await session.execute(
        select(Lesson.id, Lesson.content, Lesson.source_run_id, Lesson.created_at)
        .where(Lesson.agent_id == agent_id)
        .order_by(Lesson.created_at.desc())
        .limit(limit)
    )
    return [dict(r) for r in res.mappings()]


# ───────────────────────── document content (view / edit / re-embed) ─────────────
async def get_document(session: AsyncSession, doc_id: str) -> dict | None:
    if not is_uuid(doc_id):
        return None
    res = await session.execute(
        select(
            Document.id, Document.kb_id, Document.filename, Document.content_type,
            Document.num_pages, Document.status, Document.created_at,
        ).where(Document.id == doc_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_document_text(session: AsyncSession, doc_id: str) -> str:
    """The faithful editable source: the stored source_text, else a chunk-join fallback
    (older docs ingested before source_text existed)."""
    if not is_uuid(doc_id):
        return ""
    src = await session.scalar(select(Document.source_text).where(Document.id == doc_id))
    if src is not None:
        return src
    res = await session.execute(
        select(Chunk.content).where(Chunk.document_id == doc_id).order_by(Chunk.ordinal)
    )
    return "\n\n".join(r[0] for r in res.all())


async def get_page_index(session: AsyncSession, doc_id: str) -> list[dict]:
    """The structural page/section index rows for a document (the tree)."""
    if not is_uuid(doc_id):
        return []
    res = await session.execute(
        select(
            PageIndex.id, PageIndex.parent_id, PageIndex.kind, PageIndex.label,
            PageIndex.page_number, PageIndex.section_path, PageIndex.char_start, PageIndex.char_end,
        )
        .where(PageIndex.document_id == doc_id)
        .order_by(PageIndex.char_start)
    )
    return [dict(r) for r in res.mappings()]


async def clear_document_index(session: AsyncSession, doc_id: str) -> None:
    """Drop a document's chunks + page index (before a re-ingest of edited text)."""
    if not is_uuid(doc_id):
        return
    await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
    await session.execute(delete(PageIndex).where(PageIndex.document_id == doc_id))


async def replace_document_index(
    session: AsyncSession, doc_id: str, *, page_rows: list[dict], chunk_rows: list[dict],
    source_text: str, num_pages: int,
) -> None:
    """Atomically swap a document's index: drop old chunks/page_index, insert the new
    rows, and set source_text + ready status — all in the caller's single transaction,
    so a crash before commit leaves the old content intact."""
    await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
    await session.execute(delete(PageIndex).where(PageIndex.document_id == doc_id))
    if page_rows:
        await session.execute(insert(PageIndex), page_rows)
    if chunk_rows:
        await session.execute(insert(Chunk), chunk_rows)
    await session.execute(
        update(Document).where(Document.id == doc_id)
        .values(source_text=source_text, num_pages=num_pages, status="ready", error=None)
    )
