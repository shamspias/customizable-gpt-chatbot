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
