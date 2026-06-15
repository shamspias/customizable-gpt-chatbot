"""The `kb.search` tool — the only first-party tool in the MVP.

Defined here as a leaf (depends only on veldra_mcp); the actual retrieval function
is dependency-injected by veldra_app so this package doesn't import the service.
At v1 this becomes a real MCP server; the schema and logical name stay identical.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from veldra_mcp import Tool, ToolContext, ToolResult

# search_fn(query, kb_ids, tenant_id, k) -> (model_facing_text, citations)
SearchFn = Callable[..., Awaitable[tuple[str, list[dict]]]]

INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "query": {"type": "string", "description": "Natural-language search query."},
        "k": {
            "type": "integer",
            "description": "Number of chunks to retrieve (default 6).",
        },
        "mode": {
            "type": "string",
            "enum": ["semantic", "keyword", "hybrid"],
            "description": "Optional retrieval mode override (defaults to the KB's setting).",
        },
    },
    "required": ["query"],
}

DESCRIPTION = (
    "Search the agent's attached knowledge base(s) and return the most relevant "
    "passages with citations (document, page, section). Call this whenever the "
    "answer depends on the user's documents rather than general knowledge."
)


def build_tool(search_fn: SearchFn) -> Tool:
    async def handler(args: dict, ctx: ToolContext) -> ToolResult:
        query = (args.get("query") or "").strip()
        if not query:
            return ToolResult(content="Error: 'query' is required.", is_error=True)
        k = int(args.get("k") or 6)
        mode = args.get("mode") or None
        if not ctx.knowledge_bases:
            return ToolResult(
                content="No knowledge base is attached to this agent.",
                data={"citations": []},
            )
        text, citations = await search_fn(
            query=query, kb_ids=ctx.knowledge_bases, tenant_id=ctx.tenant_id, k=k, mode=mode
        )
        return ToolResult(content=text, data={"citations": citations}, is_error=False)

    return Tool(
        name="kb.search",
        description=DESCRIPTION,
        input_schema=INPUT_SCHEMA,
        handler=handler,
        parallel_safe=True,
    )
