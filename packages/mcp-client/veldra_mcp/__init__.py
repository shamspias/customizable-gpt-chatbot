"""veldra_mcp — MCP-shaped tool registry + dispatch (in-process MVP, MCP-backed at v1)."""

from veldra_mcp.registry import (
    Handler,
    Tool,
    ToolContext,
    ToolRegistry,
    ToolResult,
    from_wire_name,
    to_wire_name,
)

__all__ = [
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    "Handler",
    "to_wire_name",
    "from_wire_name",
]
