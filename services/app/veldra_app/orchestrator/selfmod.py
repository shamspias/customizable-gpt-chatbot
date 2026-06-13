"""Config-only self-modification.

The orchestrator emits a COMPLETE revised AgentSpec; we diff it against the
current version to produce a reviewable JSON-Patch. MVP safety = schema validation
+ referential integrity + human diff-approval (no automated replay gate — that's
v1). Capability gating blocks any change that adds a non-`kb.search` tool or a
code node (those need the v1 sandbox).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import jsonpatch
from veldra_spec import AgentSpec

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.events import ev, status
from veldra_app.orchestrator.catalog import build_catalog, lint_spec, normalize
from veldra_app.orchestrator.compiler import _system_prompt, compile_with_repair, wants_workflow


# Tools that cannot be granted without the v1 execution sandbox (none yet — a
# `code`/`bash` exec tool would go here and be hard-blocked in the MVP).
DANGEROUS_TOOLS: set[str] = set()


def _tool_keys(spec: dict) -> set[str]:
    return {t["name"] for t in spec.get("tools", [])}


def classify(old: dict, new: dict) -> tuple[str, bool, list[str]]:
    """Return (capability_class, blocked, reasons).

    cosmetic   = prompt/model/effort/kb edits → low-risk.
    sensitive  = grants a new (non-kb.search) tool → needs explicit approval.
    blocked    = grants a DANGEROUS tool that requires the v1 sandbox.
    """
    added = _tool_keys(new) - _tool_keys(old)
    blocked = sorted(t for t in added if t in DANGEROUS_TOOLS)
    if blocked:
        return ("sensitive", True,
                [f"adds tool '{t}', which requires the v1 execution sandbox" for t in blocked])
    if any(t != "kb.search" for t in added):
        return "sensitive", False, []
    return "cosmetic", False, []


async def propose(agent_id: str, instruction: str, tenant_id: str) -> AsyncIterator[dict]:
    yield status("loading")
    sm = get_sessionmaker()
    async with sm() as session:
        current = await repo.get_spec(session, agent_id)
    if current is None:
        yield ev("error", message="Agent not found.")
        return

    catalog = await build_catalog(tenant_id)
    system = _system_prompt(catalog)
    user = (
        f"Here is the current AgentSpec (JSON):\n{json.dumps(current, indent=2)}\n\n"
        f"Apply this change: {instruction}\n\n"
        "Return the COMPLETE revised AgentSpec, preserving everything not affected by the change."
    )

    # Keep the workflow field available when the agent already has one (so an edit
    # doesn't silently drop it) or the instruction is about a workflow.
    include_workflow = bool(current.get("workflow_graph")) or wants_workflow(instruction)
    include_team = bool(current.get("sub_agents")) or bool(catalog.get("agents"))
    yield status("designing")
    spec, errors = await compile_with_repair(
        system, [{"role": "user", "content": user}], catalog,
        include_workflow=include_workflow, include_team=include_team,
    )
    if spec is None:
        yield ev("error", message="Couldn't produce a valid revision: " + "; ".join(errors))
        return

    new = spec.model_dump()
    patch = jsonpatch.make_patch(current, new).patch
    klass, blocked, reasons = classify(current, new)
    yield ev(
        "diff",
        agent_id=agent_id,
        summary=instruction,
        patch=patch,
        new_spec=new,
        capability_class=klass,
        blocked=blocked,
        reasons=reasons,
    )
    yield ev("done", agent_id=agent_id, blocked=blocked)


async def apply(agent_id: str, new_spec: dict, tenant_id: str) -> dict:
    """Validate + gate + persist an approved revision as a new immutable version."""
    spec = AgentSpec.model_validate(new_spec)  # schema validation
    catalog = await build_catalog(tenant_id)
    errors = lint_spec(spec, catalog)
    if errors:
        raise ValueError("invalid spec: " + "; ".join(errors))
    spec = normalize(spec, catalog)

    sm = get_sessionmaker()
    async with sm() as session:
        current = await repo.get_spec(session, agent_id)
        if current is None:
            raise ValueError("agent not found")
        klass, blocked, reasons = classify(current, spec.model_dump())
        if blocked:
            raise ValueError("change blocked: " + "; ".join(reasons))
        version = await repo.insert_spec_version(session, agent_id, spec.model_dump(), note="self-mod")
        await repo.set_current_version(session, agent_id, version)
        await repo.insert_audit(
            session, tenant_id, "orchestrator", "apply_self_mod", "agent", agent_id,
            {"version": version, "class": klass},
        )
        await session.commit()
    return {"agent_id": agent_id, "version": version, "capability_class": klass}


async def set_workflow(agent_id: str, graph: dict, tenant_id: str) -> dict:
    """Replace the agent's workflow_graph (from the visual builder) and persist a
    new version. Forgiving: auto-attaches the default KB if the graph searches docs."""
    sm = get_sessionmaker()
    async with sm() as session:
        current = await repo.get_spec(session, agent_id)
    if current is None:
        raise ValueError("agent not found")

    catalog = await build_catalog(tenant_id)
    spec = AgentSpec.model_validate({**current, "workflow_graph": graph})
    if (
        spec.workflow_graph
        and any(n.type == "kb_search" for n in spec.workflow_graph.nodes)
        and not spec.knowledge_bases
    ):
        spec = spec.model_copy(update={"knowledge_bases": [catalog["kb_id"]]})
    errors = lint_spec(spec, catalog)
    if errors:
        raise ValueError("; ".join(errors))

    async with sm() as session:
        version = await repo.insert_spec_version(
            session, agent_id, spec.model_dump(), note="workflow edit"
        )
        await repo.set_current_version(session, agent_id, version)
        await repo.insert_audit(
            session, tenant_id, "user", "set_workflow", "agent", agent_id, {"version": version}
        )
        await session.commit()
    return {"agent_id": agent_id, "version": version}
