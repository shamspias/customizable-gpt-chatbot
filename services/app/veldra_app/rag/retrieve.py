"""Retrieval for kb.search — mode-aware (semantic / keyword / hybrid) with citations.

Per-KB config governs behaviour (overridable per call):
  • retrieval_mode  semantic (vector) | keyword (lexical/BM25) | hybrid (RRF of both)
  • embedding_model the query is embedded with the SAME model the chunks were
  • rerank_model    optional second-stage cross-encoder/rerank (off by default)

Returns a model-facing numbered passage block (tagged with citations) and the
structured citation list the UI renders as clickable chips.
"""

from __future__ import annotations

from veldra_llm import embed_query

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.rag import rerank as reranker
from veldra_app.rag.ingest import embed_config
from veldra_app.rag.vectorstores import get_vector_store

RRF_K = 60
VALID_MODES = {"semantic", "keyword", "hybrid"}


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


async def _kb_config(kb_ids: list[str], tenant_id: str) -> dict:
    """The governing retrieval config = the first KB's config (agents usually have one)."""
    default = {"retrieval_mode": "hybrid", "embedding_model": None,
               "rerank_model": None, "page_index_enabled": True}
    if not kb_ids:
        return default
    sm = get_sessionmaker()
    async with sm() as session:
        kb = await repo.get_kb(session, kb_ids[0])
    return {**default, **(kb or {})}


async def search(
    query: str, kb_ids: list[str], tenant_id: str, k: int = 6, mode: str | None = None
) -> tuple[str, list[dict]]:
    cfg = await _kb_config(kb_ids, tenant_id)
    mode = (mode or cfg["retrieval_mode"] or "hybrid").lower()
    if mode not in VALID_MODES:
        mode = "hybrid"
    rerank_model = cfg.get("rerank_model")
    # Over-fetch when a second stage (RRF or rerank) will re-order the candidates.
    fetch = k * 4 if (mode == "hybrid" or reranker.is_configured(rerank_model)) else k

    sm = get_sessionmaker()
    vec_rows: list[dict] = []
    lex: list[dict] = []
    if mode in ("semantic", "hybrid"):
        emb = await embed_query(query, embed_config(cfg.get("embedding_model")))
        vec_hits = await get_vector_store().query(emb, kb_ids, tenant_id, n=fetch)
        async with sm() as session:
            rows = await repo.get_chunks_by_ids(session, [cid for cid, _ in vec_hits])
        by_id = {str(r["id"]): r for r in rows}
        vec_rows = [by_id[cid] for cid, _ in vec_hits if cid in by_id]  # preserve vector order
    if mode in ("keyword", "hybrid"):
        async with sm() as session:
            lex = await repo.lexical_search(session, tenant_id, kb_ids, query, n=fetch)

    if mode == "semantic":
        candidates = vec_rows
    elif mode == "keyword":
        candidates = lex
    else:
        candidates = _rrf(vec_rows, lex)

    fused = await reranker.rerank(query, candidates, rerank_model, top_k=k)
    if not fused:
        return ("No relevant passages were found in the knowledge base.", [])

    citations: list[dict] = []
    lines: list[str] = []
    for i, row in enumerate(fused, start=1):
        page = row.get("page_number")
        filename = row.get("filename") or "document"
        loc = f"{filename} p.{page}" if page else filename
        content = (row.get("content") or "").strip()
        citations.append({
            "index": i, "filename": filename, "page": page,
            "section_path": row.get("section_path"),
            "char_start": row.get("char_start"), "char_end": row.get("char_end"),
            "snippet": content[:240],
        })
        lines.append(f"[{i}] ({loc})\n{content}")

    header = f"Retrieved passages ({mode} search — cite the bracketed number you use):\n\n"
    return header + "\n\n".join(lines), citations
