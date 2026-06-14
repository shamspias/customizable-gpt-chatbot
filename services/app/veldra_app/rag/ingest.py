"""Document ingestion: parse -> page index -> chunk -> embed -> store."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from veldra_llm import EmbeddingConfig, embed_texts

from veldra_app import repo, storage
from veldra_app.config import DEFAULT_TENANT_ID, get_settings
from veldra_app.db import get_sessionmaker
from veldra_app.rag.chunking import chunk_page


def embed_config() -> EmbeddingConfig:
    s = get_settings()
    return EmbeddingConfig(
        provider=s.embed_provider,
        dim=s.embed_dim,
        openai_api_key=s.openai_api_key,
        openai_model=s.openai_embed_model,
        ollama_model=s.ollama_embed_model,
        ollama_base_url=s.ollama_base_url,
    )


@dataclass
class IngestResult:
    document_id: str
    kb_id: str
    filename: str
    num_pages: int
    num_chunks: int


def _parse_pages(data: bytes, filename: str, content_type: str) -> list[tuple[int, str]]:
    """Return [(page_number, text)]. PDFs page-by-page; text/markdown as one page."""
    name = filename.lower()
    if content_type == "application/pdf" or name.endswith(".pdf"):
        import pdfplumber

        pages: list[tuple[int, str]] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append((i, page.extract_text() or ""))
        return pages
    # txt / md / fallback
    try:
        return [(1, data.decode("utf-8"))]
    except UnicodeDecodeError:
        return [(1, data.decode("utf-8", errors="replace"))]


async def ingest_document(
    data: bytes,
    filename: str,
    content_type: str,
    tenant_id: str = DEFAULT_TENANT_ID,
    kb_name: str = "default",
    kb_id: str | None = None,
) -> IngestResult:
    sm = get_sessionmaker()
    s3_key = f"{tenant_id}/{uuid.uuid4()}/{filename}"
    await storage.put_object(s3_key, data, content_type or "application/octet-stream")

    async with sm() as session:
        if kb_id is None:
            kb_id = await repo.get_or_create_kb(session, tenant_id, kb_name)
        doc_id = await repo.create_document(session, kb_id, tenant_id, filename, content_type, s3_key)
        await session.commit()

    try:
        pages = _parse_pages(data, filename, content_type)

        # Build page index + chunks with document-absolute char offsets.
        page_rows: list[dict] = []
        all_chunks: list = []
        base = 0
        for page_number, text in pages:
            page_rows.append(
                {
                    "document_id": doc_id,
                    "kind": "page",
                    "label": f"Page {page_number}",
                    "page_number": page_number,
                    "section_path": None,
                    "char_start": base,
                    "char_end": base + len(text),
                }
            )
            all_chunks.extend(chunk_page(text, page_number, base))
            base += len(text) + 1  # +1 for the implicit page separator

        if not all_chunks:
            async with sm() as session:
                await repo.set_document_status(session, doc_id, "ready", num_pages=len(pages))
                await session.commit()
            return IngestResult(doc_id, kb_id, filename, len(pages), 0)

        embeddings = await embed_texts([c.content for c in all_chunks], embed_config())
        ids = [str(uuid.uuid4()) for _ in all_chunks]

        chunk_rows = [
            {
                "id": ids[i],
                "document_id": doc_id,
                "kb_id": kb_id,
                "tenant_id": tenant_id,
                "ordinal": i,
                "content": c.content,
                "page_number": c.page_number,
                "section_path": None,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "token_count": c.token_count,
                "embedding": emb,  # list[float]; pgvector adapts it on insert
            }
            for i, (c, emb) in enumerate(zip(all_chunks, embeddings, strict=True))
        ]

        async with sm() as session:
            await repo.insert_page_index(session, page_rows)
            await repo.insert_chunks(session, chunk_rows)
            await repo.set_document_status(session, doc_id, "ready", num_pages=len(pages))
            await session.commit()

        # Mirror vectors to the configured store (no-op for pgvector; upsert for qdrant).
        from veldra_app.rag.vectorstores import get_vector_store

        await get_vector_store().upsert(
            [
                {"id": ids[i], "embedding": embeddings[i], "kb_id": kb_id, "tenant_id": tenant_id}
                for i in range(len(ids))
            ]
        )
        return IngestResult(doc_id, kb_id, filename, len(pages), len(chunk_rows))
    except Exception as exc:
        async with sm() as session:
            await repo.set_document_status(session, doc_id, "failed", error=str(exc))
            await session.commit()
        raise
