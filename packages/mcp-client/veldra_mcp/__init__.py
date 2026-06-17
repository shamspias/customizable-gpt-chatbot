"""veldra_mcp — MCP-shaped tool registry + dispatch (in-process builtins + MCP-backed
external connectors behind one identical Tool contract)."""

from veldra_mcp import mcp_provider
from veldra_mcp.mcp_provider import McpServerConfig
from veldra_mcp.net import SafeResponse, check_peer, guard_url, safe_request
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
    "guard_url",
    "check_peer",
    "safe_request",
    "SafeResponse",
    "mcp_provider",
    "McpServerConfig",
]
