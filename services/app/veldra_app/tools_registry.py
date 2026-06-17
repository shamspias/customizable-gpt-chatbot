"""Builds the process-wide ToolRegistry and registers first-party tools.

MVP registers only kb.search, injecting the rag.search retrieval function so the
tool package stays a leaf. v1 adds sandboxed/MCP-backed tools behind the same
registry interface.
"""

from __future__ import annotations

import functools

from veldra_mcp import ToolRegistry
from veldra_mcp_servers import builtins, kb_search

from veldra_app.rag import search as rag_search


@functools.lru_cache
def get_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(kb_search.build_tool(rag_search))  # RAG over uploaded docs
    for tool in builtins.build_tools():  # time / math / http.fetch / fs.*
        registry.register(tool)
    return registry


async def get_catalog(tenant_id: str) -> list[dict]:
    """The tool catalog visible to a workspace. Built-ins for now; the plugin phase
    merges per-tenant plugin/MCP tools here (async so it can read the DB)."""
    return get_registry().catalog()
