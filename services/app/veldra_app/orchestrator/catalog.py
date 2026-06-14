"""Tool/KB catalog the orchestrator designs against, plus the static spec linter.

The catalog is small in the MVP (one tool, one KB) so it's inlined in the
orchestrator prompt; above ~20 tools the orchestrator would switch to a
`tool.search` tool instead (deferred).
"""

from __future__ import annotations

from veldra_spec import AgentSpec, ToolBinding

from veldra_app import repo
from veldra_app.config import DEFAULT_TENANT_ID
from veldra_app.db import get_sessionmaker
from veldra_app.tools_registry import get_registry


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

    g = spec.workflow_graph
    if g and g.nodes:
        ids = g.node_ids()
        if g.entrypoint not in ids:
            errors.append(f"workflow entrypoint '{g.entrypoint}' is not a node id")
        if not any(n.type == "end" for n in g.nodes):
            errors.append("workflow must contain an 'end' node")
        for e in g.edges:
            if e.source not in ids:
                errors.append(f"workflow edge source '{e.source}' is not a node id")
            if e.target not in ids:
                errors.append(f"workflow edge target '{e.target}' is not a node id")
        if any(n.type == "kb_search" for n in g.nodes) and not spec.knowledge_bases:
            errors.append("workflow uses kb_search but no knowledge base is attached")
        # Per-node integrity for the rich node set (guides the repair loop).
        outgoing = {e.source for e in g.edges}
        for n in g.nodes:
            c = n.config
            branches = {e.when for e in g.edges if e.source == n.id}
            if n.type == "tool" and c.tool not in allowed:
                errors.append(
                    f"workflow node '{n.id}' uses tool '{c.tool}' — choose from {sorted(allowed)}"
                )
            if n.type == "classifier":
                if not c.classes:
                    errors.append(f"classifier node '{n.id}' must list `classes`")
                else:
                    missing = [cl for cl in c.classes if cl not in branches]
                    if missing:
                        errors.append(
                            f"classifier '{n.id}' needs an edge with when=<class> for each of {missing}"
                        )
            if n.type in ("if_else", "condition") and not c.var:
                errors.append(f"{n.type} node '{n.id}' must set `var` (the variable to test)")
            if n.type != "end" and n.id not in outgoing:
                errors.append(f"node '{n.id}' has no outgoing edge (dead end before 'end')")
    return errors


def normalize(spec: AgentSpec, catalog: dict) -> AgentSpec:
    """Harmless fixups that don't warrant a repair round-trip: dedupe tools, force
    kb.search to auto (read-only), and reconcile kb.search ⟷ knowledge_bases."""
    tools: list[ToolBinding] = []
    seen: set[str] = set()
    for t in spec.tools:
        if t.name in seen:
            continue
        seen.add(t.name)
        if t.name == "kb.search":
            t = t.model_copy(update={"permission_mode": "auto"})
        tools.append(t)

    kbs = list(dict.fromkeys(spec.knowledge_bases))
    has_kb_tool = "kb.search" in seen
    if kbs and not has_kb_tool:
        tools.append(
            ToolBinding(name="kb.search", permission_mode="auto",
                        reason="answer from the attached documents")
        )
    elif has_kb_tool and not kbs:
        kbs = [catalog["kb_id"]]

    return spec.model_copy(update={"tools": tools, "knowledge_bases": kbs})
