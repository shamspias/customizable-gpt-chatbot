"""Pluggable reranking — the optional second stage of retrieval.

A reranker re-scores the first-stage candidates against the query with a
cross-encoder / rerank model, which sharply improves precision@k. It's OFF by
default (local-first, no cloud key required) and selected per-KB via a
"provider:model" string:

  cohere:rerank-3.5          → Cohere Rerank API   (needs COHERE_API_KEY)
  jina:jina-reranker-v2-base → Jina Rerank API     (needs JINA_API_KEY)
  local:BAAI/bge-reranker-base → sentence-transformers CrossEncoder (lazy import)

Any failure (missing key, model not installed, network) degrades gracefully:
retrieval keeps the first-stage order instead of erroring.
"""

from __future__ import annotations

import os

import httpx

COHERE_URL = "https://api.cohere.com/v2/rerank"
JINA_URL = "https://api.jina.ai/v1/rerank"


def is_configured(model_spec: str | None) -> bool:
    return bool(model_spec and ":" in model_spec)


async def rerank(query: str, rows: list[dict], model_spec: str | None, top_k: int) -> list[dict]:
    """Return rows reordered by relevance to query; falls back to rows[:top_k] on any issue."""
    if not is_configured(model_spec) or not rows:
        return rows[:top_k]
    provider, _, model = model_spec.partition(":")
    docs = [str(r.get("content") or "") for r in rows]
    try:
        if provider == "cohere":
            order = await _cohere(query, docs, model)
        elif provider == "jina":
            order = await _jina(query, docs, model)
        elif provider in ("local", "st"):
            order = _cross_encoder(query, docs, model)
        else:
            return rows[:top_k]
    except Exception:  # never let reranking break retrieval
        return rows[:top_k]
    ranked = [rows[i] for i in order if 0 <= i < len(rows)]
    return ranked[:top_k] if ranked else rows[:top_k]


async def _cohere(query: str, docs: list[str], model: str) -> list[int]:
    key = os.getenv("COHERE_API_KEY", "")
    if not key:
        raise RuntimeError("COHERE_API_KEY not set")
    payload = {"model": model or "rerank-3.5", "query": query, "documents": docs}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(COHERE_URL, json=payload, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        results = r.json()["results"]
    return [item["index"] for item in results]


async def _jina(query: str, docs: list[str], model: str) -> list[int]:
    key = os.getenv("JINA_API_KEY", "")
    if not key:
        raise RuntimeError("JINA_API_KEY not set")
    model = model or "jina-reranker-v2-base-multilingual"
    payload = {"model": model, "query": query, "documents": docs}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(JINA_URL, json=payload, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        results = r.json()["results"]
    return [item["index"] for item in results]


def _cross_encoder(query: str, docs: list[str], model: str) -> list[int]:
    from sentence_transformers import CrossEncoder  # lazy: optional heavy dep

    ce = CrossEncoder(model or "BAAI/bge-reranker-base")
    scores = ce.predict([(query, d) for d in docs])
    return sorted(range(len(docs)), key=lambda i: float(scores[i]), reverse=True)
