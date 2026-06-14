"""Platform-admin tools — the toolset of the built-in **Faust** bot.

These let Faust manage the platform itself: list/rename/update/tag/delete agents,
inspect + clear the activity log, and delete knowledge-base documents. They are
DELIBERATELY kept out of the default tool registry (tools_registry.get_registry) so a
normal user-built agent can never be granted them — Faust runs with its own registry
(see veldra_app.faust). Each handler is tenant-scoped via ToolContext.tenant_id.
"""

from __future__ import annotations

import json

from veldra_mcp import Tool, ToolContext, ToolResult

from veldra_app import repo
from veldra_app.db import get_sessionmaker

_STR = {"type": "string"}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": required}


async def _resolve_agent(session, tenant_id: str, ref: str) -> dict | None:
    """Resolve an agent by id or (case-insensitive) name."""
    ref = (ref or "").strip()
    if repo.is_uuid(ref):
        a = await repo.get_agent(session, ref)
        if a:
            return a
    for a in await repo.list_agents(session, tenant_id):
        if a["name"].lower() == ref.lower():
            return a
    return None


async def _list_agents(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.list_agents(s, ctx.tenant_id)
    listing = [{"name": r["name"], "tags": r.get("tags") or [], "version": r["current_version"]}
               for r in rows]
    return ToolResult(content=json.dumps(listing) or "[]")


async def _rename_agent(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    new_name = (args.get("new_name") or "").strip()
    if not new_name:
        return ToolResult(content="Error: new_name is required.", is_error=True)
    async with sm() as s:
        a = await _resolve_agent(s, ctx.tenant_id, args.get("name", ""))
        if not a:
            return ToolResult(content=f"No agent named '{args.get('name')}'.", is_error=True)
        try:
            await repo.rename_agent(s, str(a["id"]), new_name)
            await repo.insert_audit(s, ctx.tenant_id, "faust", "rename_agent", "agent",
                                    str(a["id"]), {"from": a["name"], "to": new_name})
            await s.commit()
        except Exception as exc:
            return ToolResult(content=f"Rename failed: {exc}", is_error=True)
    return ToolResult(content=f"Renamed '{a['name']}' → '{new_name}'.")


async def _update_policy(args: dict, ctx: ToolContext) -> ToolResult:
    from veldra_app.orchestrator import selfmod

    sm = get_sessionmaker()
    prompt = (args.get("system_prompt") or "").strip()
    if not prompt:
        return ToolResult(content="Error: system_prompt is required.", is_error=True)
    async with sm() as s:
        a = await _resolve_agent(s, ctx.tenant_id, args.get("name", ""))
        if not a:
            return ToolResult(content=f"No agent named '{args.get('name')}'.", is_error=True)
        spec = await repo.get_spec(s, str(a["id"]))
    try:
        res = await selfmod.apply(str(a["id"]), {**spec, "system_prompt": prompt}, ctx.tenant_id)
    except ValueError as exc:
        return ToolResult(content=f"Update failed: {exc}", is_error=True)
    return ToolResult(content=f"Updated '{a['name']}' policy (now v{res['version']}).")


async def _tag_agent(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    tags = [t.strip() for t in (args.get("tags") or "").split(",") if t.strip()]
    async with sm() as s:
        a = await _resolve_agent(s, ctx.tenant_id, args.get("name", ""))
        if not a:
            return ToolResult(content=f"No agent named '{args.get('name')}'.", is_error=True)
        await repo.set_agent_tags(s, str(a["id"]), tags)
        await s.commit()
    return ToolResult(content=f"Set tags on '{a['name']}': {tags}")


async def _delete_agent(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    async with sm() as s:
        a = await _resolve_agent(s, ctx.tenant_id, args.get("name", ""))
        if not a:
            return ToolResult(content=f"No agent named '{args.get('name')}'.", is_error=True)
        n = await repo.delete_agents(s, ctx.tenant_id, [str(a["id"])])
        await repo.insert_audit(s, ctx.tenant_id, "faust", "delete_agent", "agent",
                                str(a["id"]), {"name": a["name"]})
        await s.commit()
    return ToolResult(content=f"Deleted agent '{a['name']}'." if n else "Nothing deleted.")


async def _list_runs(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    kind = (args.get("kind") or "").strip().lower()
    async with sm() as s:
        rows = await repo.list_runs(s, ctx.tenant_id, limit=40)
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    out = [{"id": str(r["id"]), "kind": r["kind"], "status": r["status"],
            "agent": r.get("agent_name"), "at": str(r.get("created_at"))} for r in rows[:25]]
    return ToolResult(content=json.dumps(out, default=str) or "[]")


async def _clear_runs(args: dict, ctx: ToolContext) -> ToolResult:
    """Delete activity-log runs, optionally only those of a given kind (build|ask|selfmod).

    Deletes in one statement (no row cap) so a 'clear all logs' never silently leaves
    older runs behind, and the reported count is exact."""
    sm = get_sessionmaker()
    kind = (args.get("kind") or "").strip().lower() or None
    async with sm() as s:
        n = await repo.delete_all_runs(s, ctx.tenant_id, kind)
        await repo.insert_audit(s, ctx.tenant_id, "faust", "clear_runs", "runs", None,
                                {"kind": kind or "all", "deleted": n})
        await s.commit()
    suffix = f" of kind '{kind}'." if kind else "."
    return ToolResult(content=f"Deleted {n} activity-log run(s){suffix}")


async def _delete_document(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    fname = (args.get("filename") or "").strip().lower()
    if not fname:
        return ToolResult(content="Error: filename is required.", is_error=True)
    async with sm() as s:
        kbs = await repo.list_kbs(s, ctx.tenant_id)
        deleted = 0
        for kb in kbs:
            docs = await repo.list_documents(s, str(kb["id"]))
            ids = [str(d["id"]) for d in docs if fname in d["filename"].lower()]
            deleted += await repo.delete_documents(s, str(kb["id"]), ids)
        await s.commit()
    return ToolResult(content=f"Deleted {deleted} document(s) matching '{fname}'.")


def build_admin_tools() -> list[Tool]:
    return [
        Tool("admin.list_agents", "List all agents with their tags and current version.",
             _obj({}, []), _list_agents, True),
        Tool("admin.rename_agent", "Rename an agent (by current name or id).",
             _obj({"name": _STR, "new_name": _STR}, ["name", "new_name"]), _rename_agent, False),
        Tool("admin.update_agent", "Replace an agent's policy / system prompt.",
             _obj({"name": _STR, "system_prompt": _STR}, ["name", "system_prompt"]),
             _update_policy, False),
        Tool("admin.tag_agent", "Set an agent's tags (comma-separated).",
             _obj({"name": _STR, "tags": _STR}, ["name", "tags"]), _tag_agent, False),
        Tool("admin.delete_agent", "Delete an agent (by name or id).",
             _obj({"name": _STR}, ["name"]), _delete_agent, False),
        Tool("admin.list_runs", "List recent activity-log runs; optional kind=build|ask|selfmod.",
             _obj({"kind": _STR}, []), _list_runs, True),
        Tool("admin.clear_runs", "Delete activity-log runs; optional kind=build|ask|selfmod.",
             _obj({"kind": _STR}, []), _clear_runs, False),
        Tool("admin.delete_document",
             "Delete knowledge-base documents whose filename contains the text.",
             _obj({"filename": _STR}, ["filename"]), _delete_document, False),
    ]
