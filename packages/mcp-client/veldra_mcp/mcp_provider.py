"""MCP-backed tool provider — connect to an external MCP server (Streamable HTTP,
SSE, or stdio) and expose its tools through the same Tool contract the in-process
registry uses, so agents and the AgentSpec never change when tools live out-of-process.

Sessions are short-lived (opened per list/call) — simple and correct; a connection
pool is a later optimization. All operations are wrapped in a timeout so a dead or
slow server can never hang an agent run.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TIMEOUT = 25.0


@dataclass
class McpServerConfig:
    """How to reach one MCP server. `transport` is http | sse | stdio."""

    transport: str = "http"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT


@asynccontextmanager
async def _session(cfg: McpServerConfig):
    # Imported lazily so the leaf package imports even if `mcp` transports shift.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client

    transport = (cfg.transport or "http").lower()
    if transport in ("http", "streamable_http", "streamable-http"):
        if not cfg.url:
            raise ValueError("http transport requires a url")
        async with streamablehttp_client(cfg.url, headers=cfg.headers or None) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    elif transport == "sse":
        if not cfg.url:
            raise ValueError("sse transport requires a url")
        async with sse_client(cfg.url, headers=cfg.headers or None) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    elif transport == "stdio":
        if not cfg.command:
            raise ValueError("stdio transport requires a command")
        params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env or None)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        raise ValueError(f"unknown MCP transport: {cfg.transport!r}")


def _content_to_text(content: Any) -> str:
    """Flatten an MCP tool result's content blocks into plain text for the model."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content if isinstance(content, list) else [content]:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(str(text))
            continue
        data = getattr(block, "data", None)
        if data is not None:
            parts.append(f"[{getattr(block, 'mimeType', 'binary')} content]")
            continue
        parts.append(str(block))
    return "\n".join(p for p in parts if p)


async def list_tools(cfg: McpServerConfig) -> list[dict[str, Any]]:
    """Discover a server's tools as [{name, description, input_schema}]."""
    async with asyncio.timeout(cfg.timeout):
        async with _session(cfg) as session:
            result = await session.list_tools()
            out: list[dict[str, Any]] = []
            for t in result.tools:
                out.append({
                    "name": t.name,
                    "description": getattr(t, "description", "") or "",
                    "input_schema": getattr(t, "inputSchema", None)
                    or {"type": "object", "properties": {}},
                })
            return out


async def call_tool(cfg: McpServerConfig, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Call one tool. Returns (text, is_error)."""
    async with asyncio.timeout(cfg.timeout):
        async with _session(cfg) as session:
            result = await session.call_tool(name, args or {})
            text = _content_to_text(getattr(result, "content", None))
            is_error = bool(getattr(result, "isError", False))
            if not text and getattr(result, "structuredContent", None):
                import json
                text = json.dumps(result.structuredContent)[:8000]
            return text or "(no output)", is_error


async def probe(cfg: McpServerConfig) -> dict[str, Any]:
    """Connectivity check for the install UI: {ok, tools, error}."""
    try:
        tools = await list_tools(cfg)
        return {"ok": True, "tools": tools, "error": ""}
    except Exception as exc:  # noqa: BLE001 — reported to the UI
        return {"ok": False, "tools": [], "error": str(exc)[:400]}
