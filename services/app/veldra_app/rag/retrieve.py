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


_DEFAULT_CFG = {"retrieval_mode": "hybrid", "embedding_model": None,
                "rerank_model": None, "page_index_enabled": True}


async def _kb_configs(kb_ids: list[str], tenant_id: str) -> list[dict]:
    """Per-KB config rows (with defaults), in kb_ids order."""
    if not kb_ids:
        return []
    sm = get_sessionmaker()
    out: list[dict] = []
    async with sm() as session:
        for kid in kb_ids:
            kb = await repo.get_kb(session, kid)
            if kb:
                out.append({**_DEFAULT_CFG, **kb})
    return out


def _group_by_model(cfgs: list[dict], kb_ids: list[str]) -> dict[str | None, list[str]]:
    """Group KB ids by embedding model so each group is queried in its own vector space."""
    if not cfgs:
        return {None: kb_ids}
    groups: dict[str | None, list[str]] = {}
    for kb in cfgs:
        groups.setdefault(kb.get("embedding_model"), []).append(kb["id"])
    return groups


async def search(
    query: str, kb_ids: list[str], tenant_id: str, k: int = 6, mode: str | None = None
) -> tuple[str, list[dict]]:
    cfgs = await _kb_configs(kb_ids, tenant_id)
    gov = cfgs[0] if cfgs else _DEFAULT_CFG  # governing mode/rerank = first KB
    mode = (mode or gov["retrieval_mode"] or "hybrid").lower()
    if mode not in VALID_MODES:
        mode = "hybrid"
    rerank_model = gov.get("rerank_model")
    # Over-fetch when a second stage (RRF or rerank) will re-order the candidates.
    fetch = k * 4 if (mode == "hybrid" or reranker.is_configured(rerank_model)) else k

    sm = get_sessionmaker()
    vec_rows: list[dict] = []
    lex: list[dict] = []
    if mode in ("semantic", "hybrid"):
        # Embed the query once PER embedding model and search only that model's KBs —
        # never compare a query vector against chunks from a different embedding space.
        for model, group_kbs in _group_by_model(cfgs, kb_ids).items():
            emb = await embed_query(query, embed_config(model))
            vec_hits = await get_vector_store().query(emb, group_kbs, tenant_id, n=fetch)
            async with sm() as session:
                rows = await repo.get_chunks_by_ids(session, [cid for cid, _ in vec_hits])
            by_id = {str(r["id"]): r for r in rows}
            vec_rows.extend(by_id[cid] for cid, _ in vec_hits if cid in by_id)
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
