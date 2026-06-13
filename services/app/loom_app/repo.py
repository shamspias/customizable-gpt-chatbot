"""Async data access (raw parameterized SQL over the SQLAlchemy async engine).

JSONB params are passed as json.dumps(...) + CAST(:p AS jsonb); uuids as str +
CAST(:p AS uuid); embeddings as a pgvector literal '[..]' + CAST(:p AS vector).
Callers manage the transaction (commit on the session).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


# ───────────────────────── knowledge bases / documents ─────────────────────────
async def get_or_create_kb(session: AsyncSession, tenant_id: str, name: str = "default") -> str:
    row = (
        await session.execute(
            text(
                "SELECT id FROM knowledge_bases "
                "WHERE tenant_id = CAST(:t AS uuid) AND name = :n"
            ),
            {"t": tenant_id, "n": name},
        )
    ).first()
    if row:
        return str(row[0])
    new_id = (
        await session.execute(
            text(
                "INSERT INTO knowledge_bases (tenant_id, name) "
                "VALUES (CAST(:t AS uuid), :n) RETURNING id"
            ),
            {"t": tenant_id, "n": name},
        )
    ).scalar_one()
    return str(new_id)


async def create_document(
    session: AsyncSession,
    kb_id: str,
    tenant_id: str,
    filename: str,
    content_type: str,
    s3_key: str,
) -> str:
    return str(
        (
            await session.execute(
                text(
                    "INSERT INTO documents (kb_id, tenant_id, filename, content_type, s3_key) "
                    "VALUES (CAST(:kb AS uuid), CAST(:t AS uuid), :f, :ct, :k) RETURNING id"
                ),
                {"kb": kb_id, "t": tenant_id, "f": filename, "ct": content_type, "k": s3_key},
            )
        ).scalar_one()
    )


async def set_document_status(
    session: AsyncSession,
    doc_id: str,
    status: str,
    num_pages: int | None = None,
    error: str | None = None,
) -> None:
    await session.execute(
        text(
            "UPDATE documents SET status = :s, num_pages = COALESCE(:np, num_pages), "
            "error = :e WHERE id = CAST(:id AS uuid)"
        ),
        {"s": status, "np": num_pages, "e": error, "id": doc_id},
    )


async def insert_page_index(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    await session.execute(
        text(
            "INSERT INTO page_index "
            "(document_id, kind, label, page_number, section_path, char_start, char_end) "
            "VALUES (CAST(:document_id AS uuid), :kind, :label, :page_number, "
            ":section_path, :char_start, :char_end)"
        ),
        rows,
    )


async def insert_chunks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Each row: document_id, kb_id, tenant_id, ordinal, content, page_number,
    section_path, char_start, char_end, token_count, embedding (pgvector literal str)."""
    if not rows:
        return
    await session.execute(
        text(
            "INSERT INTO chunks (document_id, kb_id, tenant_id, ordinal, content, "
            "page_number, section_path, char_start, char_end, token_count, embedding) "
            "VALUES (CAST(:document_id AS uuid), CAST(:kb_id AS uuid), CAST(:tenant_id AS uuid), "
            ":ordinal, :content, :page_number, :section_path, :char_start, :char_end, "
            ":token_count, CAST(:embedding AS vector))"
        ),
        rows,
    )


async def vector_search(
    session: AsyncSession, tenant_id: str, kb_ids: list[str], emb: list[float], n: int
) -> list[dict]:
    res = await session.execute(
        text(
            "SELECT c.id, c.content, c.page_number, c.section_path, c.char_start, c.char_end, "
            "d.filename, (c.embedding <=> CAST(:emb AS vector)) AS distance "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.tenant_id = CAST(:t AS uuid) AND c.kb_id = ANY(:kbs) "
            "ORDER BY c.embedding <=> CAST(:emb AS vector) LIMIT :n"
        ),
        {"emb": vec_literal(emb), "t": tenant_id, "kbs": kb_ids, "n": n},
    )
    return [dict(r._mapping) for r in res]


async def lexical_search(
    session: AsyncSession, tenant_id: str, kb_ids: list[str], query: str, n: int
) -> list[dict]:
    res = await session.execute(
        text(
            "SELECT c.id, c.content, c.page_number, c.section_path, c.char_start, c.char_end, "
            "d.filename, ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) AS rank "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.tenant_id = CAST(:t AS uuid) AND c.kb_id = ANY(:kbs) "
            "AND c.tsv @@ plainto_tsquery('english', :q) "
            "ORDER BY rank DESC LIMIT :n"
        ),
        {"q": query, "t": tenant_id, "kbs": kb_ids, "n": n},
    )
    return [dict(r._mapping) for r in res]


# ───────────────────────── agents / specs (versioned) ─────────────────────────
async def get_agent_by_name(session: AsyncSession, tenant_id: str, name: str) -> dict | None:
    row = (
        await session.execute(
            text(
                "SELECT id, name, current_version FROM agents "
                "WHERE tenant_id = CAST(:t AS uuid) AND name = :n"
            ),
            {"t": tenant_id, "n": name},
        )
    ).first()
    return dict(row._mapping) if row else None


async def get_agent(session: AsyncSession, agent_id: str) -> dict | None:
    row = (
        await session.execute(
            text("SELECT id, tenant_id, name, current_version FROM agents WHERE id = CAST(:id AS uuid)"),
            {"id": agent_id},
        )
    ).first()
    return dict(row._mapping) if row else None


async def insert_spec_version(
    session: AsyncSession, agent_id: str, spec: dict, note: str | None = None
) -> int:
    version = (
        await session.execute(
            text(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM agent_specs "
                "WHERE agent_id = CAST(:a AS uuid)"
            ),
            {"a": agent_id},
        )
    ).scalar_one()
    await session.execute(
        text(
            "INSERT INTO agent_specs (agent_id, version, spec, note) "
            "VALUES (CAST(:a AS uuid), :v, CAST(:s AS jsonb), :note)"
        ),
        {"a": agent_id, "v": version, "s": json.dumps(spec), "note": note},
    )
    return int(version)


async def set_current_version(session: AsyncSession, agent_id: str, version: int) -> None:
    await session.execute(
        text("UPDATE agents SET current_version = :v WHERE id = CAST(:a AS uuid)"),
        {"v": version, "a": agent_id},
    )


async def upsert_agent_spec(
    session: AsyncSession, tenant_id: str, name: str, spec: dict, note: str | None = None
) -> tuple[str, int]:
    """Create a fresh agent (version 1) or append a new version to an existing one."""
    existing = await get_agent_by_name(session, tenant_id, name)
    if existing is None:
        agent_id = str(
            (
                await session.execute(
                    text(
                        "INSERT INTO agents (tenant_id, name, current_version) "
                        "VALUES (CAST(:t AS uuid), :n, 1) RETURNING id"
                    ),
                    {"t": tenant_id, "n": name},
                )
            ).scalar_one()
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
    if version is None:
        row = (
            await session.execute(
                text(
                    "SELECT s.spec, s.version FROM agent_specs s "
                    "JOIN agents a ON a.id = s.agent_id AND a.current_version = s.version "
                    "WHERE s.agent_id = CAST(:a AS uuid)"
                ),
                {"a": agent_id},
            )
        ).first()
    else:
        row = (
            await session.execute(
                text(
                    "SELECT spec, version FROM agent_specs "
                    "WHERE agent_id = CAST(:a AS uuid) AND version = :v"
                ),
                {"a": agent_id, "v": version},
            )
        ).first()
    if not row:
        return None
    spec = row._mapping["spec"]
    return spec if isinstance(spec, dict) else json.loads(spec)


async def list_agents(session: AsyncSession, tenant_id: str) -> list[dict]:
    res = await session.execute(
        text(
            "SELECT a.id, a.name, a.current_version, a.created_at "
            "FROM agents a WHERE a.tenant_id = CAST(:t AS uuid) ORDER BY a.created_at DESC"
        ),
        {"t": tenant_id},
    )
    return [dict(r._mapping) for r in res]


# ───────────────────────── runs / steps / audit ─────────────────────────
async def get_run_by_idem(session: AsyncSession, tenant_id: str, key: str) -> dict | None:
    row = (
        await session.execute(
            text(
                "SELECT id, status, result, agent_id, agent_version FROM runs "
                "WHERE tenant_id = CAST(:t AS uuid) AND idempotency_key = :k"
            ),
            {"t": tenant_id, "k": key},
        )
    ).first()
    return dict(row._mapping) if row else None


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
        (
            await session.execute(
                text(
                    "INSERT INTO runs (tenant_id, kind, input, idempotency_key, agent_id, agent_version) "
                    "VALUES (CAST(:t AS uuid), :kind, CAST(:in AS jsonb), :idem, "
                    "CAST(:a AS uuid), :ver) RETURNING id"
                ),
                {
                    "t": tenant_id,
                    "kind": kind,
                    "in": json.dumps(input),
                    "idem": idempotency_key,
                    "a": agent_id,
                    "ver": agent_version,
                },
            )
        ).scalar_one()
    )


async def finish_run(
    session: AsyncSession,
    run_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    await session.execute(
        text(
            "UPDATE runs SET status = :s, result = CAST(:r AS jsonb), error = :e, "
            "finished_at = now() WHERE id = CAST(:id AS uuid)"
        ),
        {"s": status, "r": json.dumps(result) if result is not None else None, "e": error, "id": run_id},
    )


async def insert_run_step(
    session: AsyncSession, run_id: str, ordinal: int, type: str, name: str | None, payload: dict
) -> None:
    await session.execute(
        text(
            "INSERT INTO run_steps (run_id, ordinal, type, name, payload) "
            "VALUES (CAST(:r AS uuid), :o, :ty, :n, CAST(:p AS jsonb))"
        ),
        {"r": run_id, "o": ordinal, "ty": type, "n": name, "p": json.dumps(payload, default=str)},
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
        text(
            "INSERT INTO audit (tenant_id, actor, action, target_type, target_id, detail) "
            "VALUES (CAST(:t AS uuid), :ac, :action, :tt, :ti, CAST(:d AS jsonb))"
        ),
        {
            "t": tenant_id,
            "ac": actor,
            "action": action,
            "tt": target_type,
            "ti": target_id,
            "d": json.dumps(detail, default=str),
        },
    )
