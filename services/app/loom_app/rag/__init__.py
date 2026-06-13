"""loom_app.rag — page-index ingestion + hybrid retrieval (the kb.search backend)."""

from loom_app.rag.ingest import IngestResult, ingest_document
from loom_app.rag.retrieve import search

__all__ = ["ingest_document", "IngestResult", "search"]
