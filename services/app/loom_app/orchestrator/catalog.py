"""Tool/KB catalog the orchestrator designs against, plus the static spec linter.

The catalog is small in the MVP (one tool, one KB) so it's inlined in the
orchestrator prompt; above ~20 tools the orchestrator would switch to a
`tool.search` tool instead (deferred).
"""

from __future__ import annotations

from loom_spec import AgentSpec, ToolBinding

from loom_app import repo
from loom_app.config import DEFAULT_TENANT_ID
from loom_app.db import get_sessionmaker
from loom_app.tools_registry import get_registry


async def build_catalog(tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    registry = get_registry()
    sm = get_sessionmaker()
    async with sm() as session:
        kb_id = await repo.get_or_create_kb(session, tenant_id, "default")
        await session.commit()
        agents = [a["name"] for a in await repo.list_agents(session, tenant_id)]
    return {"tools": registry.catalog(), "kb_id": kb_id, "kb_name": "default", "agents": agents}


def lint_spec(spec: AgentSpec, catalog: dict) -> list[str]:
    """Referential integrity: every tool/KB/sub-agent reference must resolve.
    Constrained decoding guarantees schema-validity; this catches the rest."""
    errors: list[str] = []
    allowed = {t["name"] for t in catalog["tools"]}
    for key in spec.tool_keys():
        if key not in allowed:
            errors.append(
                f"tool '{key}' is not available — choose from {sorted(allowed)} or omit it"
            )
    valid_kbs = {catalog["kb_id"]}
    for kb in spec.knowledge_bases:
        if kb not in valid_kbs:
            errors.append(f"knowledge base id '{kb}' does not exist — use '{catalog['kb_id']}'")
    existing_agents = set(catalog.get("agents", []))
    for sub in spec.sub_agents:
        if sub == spec.name:
            errors.append(f"sub_agent '{sub}' cannot reference the agent itself")
        elif sub not in existing_agents:
            errors.append(f"sub_agent '{sub}' is not an existing agent — build it first or omit it")
    return errors


def normalize(spec: AgentSpec, catalog: dict) -> AgentSpec:
    """Harmless fixups that don't warrant a repair round-trip: dedupe tools, force
    kb.search to auto (read-only), and reconcile kb.search ⟷ knowledge_bases."""
    tools: list[ToolBinding] = []
    seen: set[str] = set()
    for t in spec.tools:
        key = f"{t.mcp_server}.{t.tool_name}"
        if key in seen:
            continue
        seen.add(key)
        if key == "kb.search":
            t = t.model_copy(update={"permission_mode": "auto"})
        tools.append(t)

    kbs = list(dict.fromkeys(spec.knowledge_bases))
    has_kb_tool = "kb.search" in seen
    if kbs and not has_kb_tool:
        tools.append(
            ToolBinding(
                mcp_server="kb",
                tool_name="search",
                permission_mode="auto",
                reason="answer from the attached documents",
            )
        )
    elif has_kb_tool and not kbs:
        kbs = [catalog["kb_id"]]

    return spec.model_copy(update={"tools": tools, "knowledge_bases": kbs})
