"""veldra_app.rag — page-index ingestion + hybrid retrieval (the kb.search backend)."""

from veldra_app.rag.ingest import IngestResult, ingest_document
from veldra_app.rag.retrieve import search

__all__ = ["ingest_document", "IngestResult", "search"]
