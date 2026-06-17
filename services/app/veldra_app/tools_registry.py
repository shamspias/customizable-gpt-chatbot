"""Builds tool registries and registers first-party tools.

Built-in tools (kb.search + the builtins: time/math/calc/http/web/fs/json/regex) are
in-process and always available. Installed plugins (MCP connectors) contribute
additional tools per workspace. ``build_registry(tenant_id)`` returns a *fresh*
registry composing builtins + that workspace's enabled plugin tools — never the
shared cached instance, so one tenant's connectors can't leak into another's.
"""

from __future__ import annotations

import functools

from veldra_mcp import ToolRegistry
from veldra_mcp_servers import builtins, kb_search

from veldra_app.rag import search as rag_search


def _register_builtins(registry: ToolRegistry) -> None:
    registry.register(kb_search.build_tool(rag_search))  # RAG over uploaded docs
    for tool in builtins.build_tools():  # time / math / calc / http / web / fs / json / regex
        registry.register(tool)


@functools.lru_cache
def get_registry() -> ToolRegistry:
    """Process-wide builtins-only registry (no tenant plugins). Cached + immutable;
    callers that need plugin tools use build_registry(tenant_id)."""
    registry = ToolRegistry()
    _register_builtins(registry)
    return registry


async def build_registry(tenant_id: str) -> ToolRegistry:
    """A fresh registry = builtins + this workspace's enabled plugin (MCP) tools.
    Plugin-loading failures degrade gracefully (builtins always remain available)."""
    registry = ToolRegistry()
    _register_builtins(registry)
    try:
        from veldra_app import plugins, plugins_repo
        from veldra_app.db import get_sessionmaker

        sm = get_sessionmaker()
        async with sm() as session:
            enabled = await plugins_repo.list_enabled(session, tenant_id)
        for row in enabled:
            for tool in await plugins.plugin_tools(row):
                registry.register(tool)
    except Exception:  # noqa: BLE001 — never let plugin loading break an agent run
        pass
    return registry


async def get_catalog(tenant_id: str) -> list[dict]:
    """Tool catalog for the workspace, each item tagged with its source (builtin vs the
    plugin that provides it) — for the orchestrator prompt, Settings, and create flow."""
    from veldra_app import plugins_repo
    from veldra_app.db import get_sessionmaker

    registry = await build_registry(tenant_id)
    plugin_names: dict[str, str] = {}
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            for p in await plugins_repo.list_enabled(session, tenant_id):
                plugin_names[p["key"]] = p["name"]
    except Exception:  # noqa: BLE001
        pass

    out: list[dict] = []
    for t in registry.catalog():
        prefix = t["name"].split(".", 1)[0]
        if prefix in plugin_names:
            out.append({**t, "source": "plugin", "plugin_key": prefix,
                        "plugin_name": plugin_names[prefix]})
        else:
            out.append({**t, "source": "builtin"})
    return out
