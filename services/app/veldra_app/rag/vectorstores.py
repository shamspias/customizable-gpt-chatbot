"""Pluggable vector stores (the vector leg of hybrid retrieval).

A VectorStore upserts embeddings keyed by chunk id and answers nearest-neighbour
queries returning (chunk_id, score). Chunk *content*, citation metadata, and the
lexical (tsvector) leg always live in Postgres — so citations are uniform and the
vector backend is swappable via VELDRA_VECTOR_STORE (pgvector | qdrant).
"""

from __future__ import annotations

import functools
import os
from typing import Protocol

from veldra_app import repo
from veldra_app.config import get_settings
from veldra_app.db import get_sessionmaker


class VectorStore(Protocol):
    name: str

    async def upsert(self, items: list[dict]) -> None:
        """items: {id, embedding: list[float], kb_id, tenant_id}."""

    async def query(
        self, embedding: list[float], kb_ids: list[str], tenant_id: str, n: int
    ) -> list[tuple[str, float]]:
        """Return up to n (chunk_id, score) candidates, best first."""


class PgVectorStore:
    """Vectors live in chunks.embedding (written by repo.insert_chunks)."""

    name = "pgvector"

    async def upsert(self, items: list[dict]) -> None:
        return  # already stored by insert_chunks

    async def query(self, embedding, kb_ids, tenant_id, n) -> list[tuple[str, float]]:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = await repo.vector_search(session, tenant_id, kb_ids, embedding, n)
        # smaller cosine distance = better; convert to a descending score
        return [(str(r["id"]), 1.0 / (1.0 + float(r["distance"]))) for r in rows]


class QdrantStore:
    """Vectors in a Qdrant collection; payload carries kb_id/tenant_id for filtering."""

    name = "qdrant"

    def __init__(self, url: str, collection: str, dim: int) -> None:
        from qdrant_client import AsyncQdrantClient  # lazy: only needed when selected

        self.client = AsyncQdrantClient(url=url)
        self.collection = collection
        self.dim = dim
        self._ready = False

    async def _ensure(self) -> None:
        if self._ready:
            return
        from qdrant_client import models

        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE),
            )
        self._ready = True

    async def upsert(self, items: list[dict]) -> None:
        from qdrant_client import models

        await self._ensure()
        points = [
            models.PointStruct(
                id=it["id"], vector=it["embedding"],
                payload={"kb_id": it["kb_id"], "tenant_id": it["tenant_id"]},
            )
            for it in items
        ]
        if points:
            await self.client.upsert(self.collection, points=points)

    async def query(self, embedding, kb_ids, tenant_id, n) -> list[tuple[str, float]]:
        from qdrant_client import models

        await self._ensure()
        flt = models.Filter(
            must=[models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id))],
            should=[models.FieldCondition(key="kb_id", match=models.MatchValue(value=k)) for k in kb_ids],
        )
        res = await self.client.search(
            self.collection, query_vector=embedding, query_filter=flt, limit=n
        )
        return [(str(p.id), float(p.score)) for p in res]


@functools.lru_cache
def get_vector_store() -> VectorStore:
    kind = os.getenv("VELDRA_VECTOR_STORE", "pgvector").lower()
    if kind == "qdrant":
        s = get_settings()
        return QdrantStore(
            os.getenv("VELDRA_QDRANT_URL", "http://localhost:6333"),
            os.getenv("VELDRA_QDRANT_COLLECTION", "veldra_chunks"),
            s.embed_dim,
        )
    return PgVectorStore()
