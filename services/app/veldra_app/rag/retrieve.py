"""Hybrid retrieval (vector + lexical, reciprocal-rank fusion) with citations.

This is the function injected into the kb.search tool. Returns a model-facing
text block (numbered passages tagged with their citation) and a structured
citation list the UI renders as clickable chips.
"""

from __future__ import annotations

from veldra_llm import embed_query

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.rag.ingest import embed_config
from veldra_app.rag.vectorstores import get_vector_store

RRF_K = 60


def _rrf(*ranked_lists: list[dict]) -> list[dict]:
    """Fuse ranked result lists by reciprocal rank, keyed on chunk id."""
    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for results in ranked_lists:
        for rank, row in enumerate(results):
            cid = str(row["id"])
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            rows.setdefault(cid, row)
    fused = [{**rows[cid], "score": sc} for cid, sc in scores.items()]
    fused.sort(key=lambda r: r["score"], reverse=True)
    return fused


async def search(query: str, kb_ids: list[str], tenant_id: str, k: int = 6) -> tuple[str, list[dict]]:
    emb = await embed_query(query, embed_config())
    # Vector leg from the configured store (pgvector / qdrant); lexical leg + content
    # from Postgres. Fuse by reciprocal rank.
    vec_hits = await get_vector_store().query(emb, kb_ids, tenant_id, n=k * 4)
    sm = get_sessionmaker()
    async with sm() as session:
        lex = await repo.lexical_search(session, tenant_id, kb_ids, query, n=k * 4)
        vec_rows = await repo.get_chunks_by_ids(session, [cid for cid, _ in vec_hits])

    by_id = {str(r["id"]): r for r in vec_rows}
    vec_ranked = [by_id[cid] for cid, _ in vec_hits if cid in by_id]  # preserve vector order
    fused = _rrf(vec_ranked, lex)[:k]
    if not fused:
        return ("No relevant passages were found in the knowledge base.", [])

    citations: list[dict] = []
    lines: list[str] = []
    for i, row in enumerate(fused, start=1):
        page = row.get("page_number")
        filename = row.get("filename") or "document"
        loc = f"{filename} p.{page}" if page else filename
        content = (row.get("content") or "").strip()
        citations.append(
            {
                "index": i,
                "filename": filename,
                "page": page,
                "section_path": row.get("section_path"),
                "char_start": row.get("char_start"),
                "char_end": row.get("char_end"),
                "snippet": content[:240],
            }
        )
        lines.append(f"[{i}] ({loc})\n{content}")

    text = (
        "Retrieved passages (cite the bracketed number you use):\n\n" + "\n\n".join(lines)
    )
    return text, citations
