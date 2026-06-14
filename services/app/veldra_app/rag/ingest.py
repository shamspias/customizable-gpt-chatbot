"""Document ingestion: parse -> page index -> chunk -> embed -> store.

Also supports editing a saved document (`reingest_text` re-embeds new content) and
ingesting a web page (`ingest_url` fetches + extracts text → page index)."""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass
from html import unescape

from veldra_llm import EmbeddingConfig, embed_texts

from veldra_app import repo, storage
from veldra_app.config import DEFAULT_TENANT_ID, get_settings
from veldra_app.db import get_sessionmaker
from veldra_app.rag.chunking import chunk_page


def embed_config(model: str | None = None) -> EmbeddingConfig:
    """Build the embedding config; an optional 'provider:model' overrides the KB's model.

    NOTE: pgvector's `embedding` column has a fixed dimension, so a per-KB model must
    match that dimension (swap models of equal dim, or use Qdrant for mixed dims)."""
    s = get_settings()
    cfg = EmbeddingConfig(
        provider=s.embed_provider,
        dim=s.embed_dim,
        openai_api_key=s.openai_api_key,
        openai_model=s.openai_embed_model,
        ollama_model=s.ollama_embed_model,
        ollama_base_url=s.ollama_base_url,
    )
    if model and ":" in model:
        provider, name = (p.strip() for p in model.split(":", 1))
        cfg.provider = provider
        if provider == "openai":
            cfg.openai_model = name
        elif provider == "ollama":
            cfg.ollama_model = name
    return cfg


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
        kb = await repo.get_kb(session, kb_id) or {}
        doc_id = await repo.create_document(session, kb_id, tenant_id, filename, content_type, s3_key)
        await session.commit()
    # Per-KB embedding model + page-index toggle govern this ingest.
    kb_embed_model = kb.get("embedding_model")
    build_page_index = kb.get("page_index_enabled", True)

    try:
        pages = _parse_pages(data, filename, content_type)
        n = await _index_pages(doc_id, kb_id, tenant_id, pages, kb_embed_model, build_page_index)
        return IngestResult(doc_id, kb_id, filename, len(pages), n)
    except Exception as exc:
        async with sm() as session:
            await repo.set_document_status(session, doc_id, "failed", error=str(exc))
            await session.commit()
        raise


async def _index_pages(
    doc_id: str, kb_id: str, tenant_id: str,
    pages: list[tuple[int, str]], kb_embed_model: str | None, build_page_index: bool,
) -> int:
    """Chunk → embed → store a document's pages (shared by ingest + re-ingest)."""
    sm = get_sessionmaker()
    page_rows: list[dict] = []
    all_chunks: list = []
    base = 0
    for page_number, text in pages:
        page_rows.append({
            "document_id": doc_id, "kind": "page", "label": f"Page {page_number}",
            "page_number": page_number, "section_path": None,
            "char_start": base, "char_end": base + len(text),
        })
        all_chunks.extend(chunk_page(text, page_number, base))
        base += len(text) + 1  # +1 for the implicit page separator

    if not all_chunks:
        async with sm() as session:
            await repo.set_document_status(session, doc_id, "ready", num_pages=len(pages))
            await session.commit()
        return 0

    embeddings = await embed_texts([c.content for c in all_chunks], embed_config(kb_embed_model))
    ids = [str(uuid.uuid4()) for _ in all_chunks]
    chunk_rows = [
        {
            "id": ids[i], "document_id": doc_id, "kb_id": kb_id, "tenant_id": tenant_id,
            "ordinal": i, "content": c.content, "page_number": c.page_number,
            "section_path": None, "char_start": c.char_start, "char_end": c.char_end,
            "token_count": c.token_count, "embedding": emb,
        }
        for i, (c, emb) in enumerate(zip(all_chunks, embeddings, strict=True))
    ]
    async with sm() as session:
        if build_page_index:
            await repo.insert_page_index(session, page_rows)
        await repo.insert_chunks(session, chunk_rows)
        await repo.set_document_status(session, doc_id, "ready", num_pages=len(pages))
        await session.commit()

    from veldra_app.rag.vectorstores import get_vector_store

    await get_vector_store().upsert(
        [{"id": ids[i], "embedding": embeddings[i], "kb_id": kb_id, "tenant_id": tenant_id}
         for i in range(len(ids))]
    )
    return len(chunk_rows)


async def reingest_text(doc_id: str, text: str, tenant_id: str = DEFAULT_TENANT_ID) -> IngestResult:
    """Replace a saved document's content with edited text and re-embed it."""
    sm = get_sessionmaker()
    async with sm() as session:
        doc = await repo.get_document(session, doc_id)
        if not doc:
            raise ValueError("document not found")
        kb = await repo.get_kb(session, doc["kb_id"]) or {}
        await repo.clear_document_index(session, doc_id)
        await repo.set_document_status(session, doc_id, "ingesting")
        await session.commit()
    try:
        n = await _index_pages(
            doc_id, doc["kb_id"], tenant_id, [(1, text)],
            kb.get("embedding_model"), kb.get("page_index_enabled", True),
        )
        return IngestResult(doc_id, doc["kb_id"], doc["filename"], 1, n)
    except Exception as exc:
        async with sm() as session:
            await repo.set_document_status(session, doc_id, "failed", error=str(exc))
            await session.commit()
        raise


def _html_to_text(html: str) -> tuple[str, str]:
    """Extract (title, readable text) from an HTML page — light, dependency-free."""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    body = re.sub(r"(?is)<(script|style|head|nav|footer|svg)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?is)<br\s*/?>", "\n", body)
    body = re.sub(r"(?is)</(p|div|h[1-6]|li|tr|section|article)>", "\n", body)
    body = re.sub(r"(?is)<[^>]+>", " ", body)
    body = unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", body).strip()
    return title, body


async def ingest_url(
    url: str, tenant_id: str = DEFAULT_TENANT_ID, kb_id: str | None = None
) -> IngestResult:
    """Fetch a web page, extract its text, and ingest it (web page index)."""
    import httpx

    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": "Veldra/0.1 (+ingest)"}) as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text
    title, text = _html_to_text(html)
    if not text.strip():
        raise ValueError("no readable text found at that URL")
    name = (title or url).strip()[:120]
    return await ingest_document(
        text.encode("utf-8"), f"{name}.md", "text/plain", tenant_id, kb_id=kb_id
    )
