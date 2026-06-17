"""Plugin bridge: turn a stored Plugin row into live tools.

* Connector templates pre-fill the install form (Shopify, Alibaba, generic).
* ``to_server_config`` merges the non-secret ``config`` with the ``secret`` (header
  values / env) into an :class:`McpServerConfig`.
* ``plugin_tools`` lists the connector's MCP tools (cached briefly) and wraps each as a
  Tool whose logical name is ``<plugin_key>.<tool>`` and whose handler proxies to the
  MCP server. Listing failures degrade to *no tools* — a dead connector never breaks a run.
"""

from __future__ import annotations

import re
import time

from veldra_mcp import McpServerConfig, Tool, ToolContext, ToolResult, mcp_provider

TOOL_OUTPUT_CAP = 16000
_LIST_TTL = 60.0  # seconds to cache a connector's tool list
# plugin_id -> (version_key, expires_monotonic, tools_meta)
_LIST_CACHE: dict[str, tuple[str, float, list[dict]]] = {}


# ───────────────────────── connector templates (install gallery) ─────────────────────────
TEMPLATES = [
    {
        "key": "shopify", "name": "Shopify", "icon": "🛍️", "transport": "http",
        "description": "Storefront / Admin commerce — products, orders, customers (Shopify MCP).",
        "url_placeholder": "https://your-shop.myshopify.com/api/mcp",
        "auth": {"header": "Authorization", "prefix": "Bearer ", "label": "Access token"},
    },
    {
        "key": "alibaba", "name": "Alibaba", "icon": "📦", "transport": "http",
        "description": "Alibaba / 1688 sourcing and product data via a configured MCP endpoint.",
        "url_placeholder": "https://your-alibaba-mcp.example.com/mcp",
        "auth": {"header": "Authorization", "prefix": "Bearer ", "label": "API key"},
    },
    {
        "key": "custom-http", "name": "Custom HTTP / SSE", "icon": "🔌", "transport": "http",
        "description": "Any Streamable-HTTP or SSE MCP server. Point at its URL and add headers.",
        "url_placeholder": "https://host/mcp",
        "auth": {"header": "Authorization", "prefix": "Bearer ", "label": "Token (optional)"},
    },
    {
        "key": "custom-stdio", "name": "Local (stdio)", "icon": "💻", "transport": "stdio",
        "description": "Run a local MCP server process (e.g. `npx -y some-mcp-server`).",
        "command_placeholder": "npx", "args_placeholder": "-y some-mcp-server",
        "auth": None,
    },
]


def to_server_config(row: dict) -> McpServerConfig:
    """Build an McpServerConfig from a plugin row that includes `config` + `secret`."""
    config = row.get("config") or {}
    secret = row.get("secret") or {}
    return McpServerConfig(
        transport=row.get("transport") or "http",
        url=config.get("url", ""),
        headers={**(config.get("headers") or {}), **(secret.get("headers") or {})},
        command=config.get("command", ""),
        args=list(config.get("args") or []),
        env={**(config.get("env") or {}), **(secret.get("env") or {})},
    )


def _sanitize(name: str) -> str:
    # Collapse runs of disallowed chars to a single "_" (never "__", which would be
    # lossy against the wire separator) and bound length.
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:48] or "tool"


def _make_handler(cfg: McpServerConfig, remote_name: str):
    async def handler(args: dict, ctx: ToolContext) -> ToolResult:
        try:
            text, is_error = await mcp_provider.call_tool(cfg, remote_name, args)
            return ToolResult(content=text[:TOOL_OUTPUT_CAP], is_error=is_error)
        except Exception as exc:  # noqa: BLE001 — surfaced to the model, never crashes the loop
            return ToolResult(content=f"Error calling {remote_name}: {exc}", is_error=True)

    return handler


async def _list_meta(plugin_id: str, version_key: str, cfg: McpServerConfig) -> list[dict]:
    cached = _LIST_CACHE.get(plugin_id)
    now = time.monotonic()
    if cached and cached[0] == version_key and cached[1] > now:
        return cached[2]
    meta = await mcp_provider.list_tools(cfg)  # may raise — caller handles
    _LIST_CACHE[plugin_id] = (version_key, now + _LIST_TTL, meta)
    return meta


async def plugin_tools(row: dict) -> list[Tool]:
    """Live Tool objects for one enabled plugin row (with `config` + `secret`)."""
    cfg = to_server_config(row)
    allow = set((row.get("config") or {}).get("tool_allowlist") or [])
    version_key = str(row.get("updated_at") or row.get("created_at") or "")
    try:
        meta = await _list_meta(str(row["id"]), version_key, cfg)
    except Exception:  # noqa: BLE001 — a down connector contributes no tools
        return []
    key = row["key"]
    out: list[Tool] = []
    seen: set[str] = set()
    for tm in meta:
        rname = tm["name"]
        if allow and rname not in allow:
            continue
        logical = f"{key}.{_sanitize(rname)}"
        if logical in seen:  # two remote names sanitized to the same logical → disambiguate
            i = 2
            while f"{logical}_{i}" in seen:
                i += 1
            logical = f"{logical}_{i}"
        seen.add(logical)
        desc = tm.get("description") or f"{key} · {rname}"
        # the handler calls the *real* remote name, so a disambiguated logical is safe
        out.append(Tool(logical, desc, tm.get("input_schema") or {"type": "object"},
                        _make_handler(cfg, rname), parallel_safe=False))
    return out


def invalidate_cache(plugin_id: str | None = None) -> None:
    if plugin_id is None:
        _LIST_CACHE.clear()
    else:
        _LIST_CACHE.pop(plugin_id, None)
