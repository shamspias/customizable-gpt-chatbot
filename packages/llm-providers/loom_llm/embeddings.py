"""Provider-pluggable text embeddings (Anthropic has no embeddings endpoint).

Default: hosted OpenAI `text-embedding-3-small` when an API key is present
(retrieval quality is the load-bearing RAG path — we don't silently degrade it).
Offline fallback: local Ollama `nomic-embed-text` with reduced quality.

Called over raw HTTP via httpx so neither the `openai` nor an Ollama SDK is a
hard dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"


@dataclass
class EmbeddingConfig:
    provider: str = "auto"  # auto | openai | ollama
    dim: int = 1536
    openai_api_key: str = ""
    openai_model: str = "text-embedding-3-small"
    ollama_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"

    def resolved_provider(self) -> str:
        if self.provider == "auto":
            return "openai" if self.openai_api_key else "ollama"
        return self.provider


async def embed_texts(texts: list[str], cfg: EmbeddingConfig) -> list[list[float]]:
    """Embed a batch of texts. Returns one vector per input, in order."""
    if not texts:
        return []
    provider = cfg.resolved_provider()
    if provider == "openai":
        return await _openai_embed(texts, cfg)
    if provider == "ollama":
        return await _ollama_embed(texts, cfg)
    raise ValueError(f"unknown embedding provider: {provider}")


async def embed_query(text: str, cfg: EmbeddingConfig) -> list[float]:
    return (await embed_texts([text], cfg))[0]


async def _openai_embed(texts: list[str], cfg: EmbeddingConfig) -> list[list[float]]:
    headers = {"Authorization": f"Bearer {cfg.openai_api_key}"}
    payload = {"model": cfg.openai_model, "input": texts}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(OPENAI_EMBED_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
    # Sort by index to guarantee input order.
    return [row["embedding"] for row in sorted(data, key=lambda r: r["index"])]


async def _ollama_embed(texts: list[str], cfg: EmbeddingConfig) -> list[list[float]]:
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/embeddings"
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            resp = await client.post(url, json={"model": cfg.ollama_model, "prompt": text})
            resp.raise_for_status()
            out.append(resp.json()["embedding"])
    return out
