"""Tool registry with an MCP-shaped contract.

A tool has a logical name `<server>.<tool>` (e.g. `kb.search`), a JSON-Schema for
its input, and an async handler. The runtime lists tools as Anthropic tool
definitions, gates each call by permission mode, and dispatches here.

MVP: tools are in-process handlers. v1: the same registry gains an MCP-backed
provider (stdio / Streamable HTTP) behind this identical interface — so agent
code and the AgentSpec never change when tools move out-of-process.

Anthropic tool names must match ^[a-zA-Z0-9_-]{1,64}$ (no dots), so the logical
name `kb.search` is presented on the wire as `kb__search` and mapped back on
dispatch.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

WIRE_SEP = "__"


def to_wire_name(logical: str) -> str:
    return logical.replace(".", WIRE_SEP)


def from_wire_name(wire: str) -> str:
    return wire.replace(WIRE_SEP, ".")


@dataclass
class ToolContext:
    """Per-run context passed to every tool handler."""

    tenant_id: str
    knowledge_bases: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    content: str  # what the model sees as the tool_result
    data: dict[str, Any] = field(default_factory=dict)  # structured, for UI/events (e.g. citations)
    is_error: bool = False


Handler = Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]


@dataclass
class Tool:
    name: str  # logical, e.g. "kb.search"
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    parallel_safe: bool = False

    def anthropic_def(self) -> dict[str, Any]:
        return {
            "name": to_wire_name(self.name),
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._by_wire: dict[str, str] = {}  # wire name -> logical name (exact, lossless)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        self._by_wire[to_wire_name(tool.name)] = tool.name

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def logical_for(self, wire_or_logical: str) -> str:
        """Resolve a wire name back to its logical name losslessly (so a '__' inside a
        plugin key or remote tool name can't corrupt dispatch). Falls back to the
        string decoding for names registered before the map existed."""
        return self._by_wire.get(wire_or_logical) or from_wire_name(wire_or_logical)

    def keys(self) -> list[str]:
        return sorted(self._tools)

    def catalog(self) -> list[dict[str, Any]]:
        """Lightweight catalog for the orchestrator (name + description)."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def anthropic_defs(self, names: list[str]) -> list[dict[str, Any]]:
        """Anthropic tool definitions for the given logical names (skips unknown)."""
        return [self._tools[n].anthropic_def() for n in names if n in self._tools]

    async def call(self, wire_or_logical: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        logical = self.logical_for(wire_or_logical)
        tool = self._tools.get(logical)
        if tool is None:
            return ToolResult(content=f"Error: unknown tool '{logical}'", is_error=True)
        try:
            return await tool.handler(args, ctx)
        except Exception as exc:  # surface tool errors back to the model, don't crash the loop
            return ToolResult(content=f"Error executing {logical}: {exc}", is_error=True)
