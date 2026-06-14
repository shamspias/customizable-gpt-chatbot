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


# ───────────────────────── create / write (Faust authors content) ─────────────────────────
async def _skill_id_by_name(s, tenant_id: str, name: str) -> str | None:
    for sk in await repo.list_skills(s, tenant_id):
        if sk["name"].lower() == (name or "").strip().lower():
            return str(sk["id"])
    return None


async def _create_skill(args: dict, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    if not name:
        return ToolResult(content="Error: name is required.", is_error=True)
    content = args.get("content") or ""
    description = args.get("description") or ""
    sm = get_sessionmaker()
    async with sm() as s:
        if await _skill_id_by_name(s, ctx.tenant_id, name):
            return ToolResult(
                content=f"A skill named '{name}' already exists; use admin.write_skill.",
                is_error=True)
        await repo.create_skill(s, ctx.tenant_id, name, description, content)
        await repo.insert_audit(s, ctx.tenant_id, "faust", "create_skill", "skill", name, {})
        await s.commit()
    return ToolResult(content=f"Created skill '{name}' ({len(content)} chars).")


async def _write_skill(args: dict, ctx: ToolContext) -> ToolResult:
    """Write/overwrite a skill's Markdown content (Faust generates the text)."""
    name = (args.get("name") or "").strip()
    content = args.get("content") or ""
    sm = get_sessionmaker()
    async with sm() as s:
        sid = await _skill_id_by_name(s, ctx.tenant_id, name)
        if not sid:  # create-on-write convenience
            await repo.create_skill(s, ctx.tenant_id, name, args.get("description") or "", content)
            await s.commit()
            return ToolResult(content=f"Created skill '{name}' with generated content.")
        await repo.update_skill(s, sid, content=content,
                                description=args.get("description") or None)
        await repo.insert_audit(s, ctx.tenant_id, "faust", "write_skill", "skill", name, {})
        await s.commit()
    return ToolResult(content=f"Updated skill '{name}' ({len(content)} chars).")


async def _delete_skill(args: dict, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    sm = get_sessionmaker()
    async with sm() as s:
        sid = await _skill_id_by_name(s, ctx.tenant_id, name)
        if not sid:
            return ToolResult(content=f"No skill named '{name}'.", is_error=True)
        await repo.delete_skill(s, sid)
        await repo.insert_audit(s, ctx.tenant_id, "faust", "delete_skill", "skill", name, {})
        await s.commit()
    return ToolResult(content=f"Deleted skill '{name}'.")


async def _list_skills(args: dict, ctx: ToolContext) -> ToolResult:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = await repo.list_skills(s, ctx.tenant_id)
    return ToolResult(content=json.dumps([{"name": r["name"], "description": r["description"]}
                                          for r in rows]) or "[]")


async def _create_kb(args: dict, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    if not name:
        return ToolResult(content="Error: name is required.", is_error=True)
    sm = get_sessionmaker()
    async with sm() as s:
        kid = await repo.create_kb(s, ctx.tenant_id, name)
        await repo.insert_audit(s, ctx.tenant_id, "faust", "create_kb", "kb", str(kid),
                                {"name": name})
        await s.commit()
    return ToolResult(content=f"Created knowledge base '{name}'.")


async def _write_document(args: dict, ctx: ToolContext) -> ToolResult:
    """Write generated text into a knowledge base as a new document (ingest + embed)."""
    from veldra_app.rag import ingest_document

    kb_name = (args.get("kb") or "default").strip()
    filename = (args.get("filename") or "note.md").strip()
    text = args.get("text") or ""
    if not text.strip():
        return ToolResult(content="Error: text is required.", is_error=True)
    sm = get_sessionmaker()
    async with sm() as s:
        kid = None
        for kb in await repo.list_kbs(s, ctx.tenant_id):
            if kb["name"].lower() == kb_name.lower():
                kid = str(kb["id"])
                break
    res = await ingest_document(text.encode("utf-8"), filename, "text/markdown",
                                ctx.tenant_id, kb_name=kb_name, kb_id=kid)
    return ToolResult(content=f"Wrote '{res.filename}' into KB ({res.num_chunks} chunks).")


async def _create_agent(args: dict, ctx: ToolContext) -> ToolResult:
    """Build a new agent (or team) from a natural-language description."""
    from veldra_app import repo as _repo
    from veldra_app.orchestrator import build_agent

    request = (args.get("request") or "").strip()
    if not request:
        return ToolResult(content="Error: request is required.", is_error=True)
    sm = get_sessionmaker()
    async with sm() as s:
        run_id = await _repo.create_run(s, ctx.tenant_id, "build", {"request": request})
        await s.commit()
    name = None
    try:
        async for ev in build_agent(request, ctx.tenant_id, run_id):
            if ev["event"] == "spec":
                name = json.loads(ev["data"]).get("spec", {}).get("name")
        async with sm() as s:  # no spec yielded = a failed build → 'error', not 'done'
            await _repo.finish_run(s, run_id, "done" if name else "error")
            await s.commit()
    except Exception as exc:  # never leak a stuck 'running' run
        async with sm() as s:
            await _repo.finish_run(s, run_id, "error", error=str(exc))
            await s.commit()
        return ToolResult(content=f"Build failed: {exc}", is_error=True)
    msg = f"Built agent '{name}'." if name else "Could not build a valid agent."
    return ToolResult(content=msg, is_error=not name)


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
        # ── create / write content ──
        Tool("admin.list_skills", "List available skills (name + description).",
             _obj({}, []), _list_skills, True),
        Tool("admin.create_skill", "Create a new skill (Markdown playbook).",
             _obj({"name": _STR, "description": _STR, "content": _STR}, ["name"]),
             _create_skill, False),
        Tool("admin.write_skill",
             "Write/overwrite a skill's Markdown content (you generate the text).",
             _obj({"name": _STR, "content": _STR, "description": _STR}, ["name", "content"]),
             _write_skill, False),
        Tool("admin.delete_skill", "Delete a skill by name.",
             _obj({"name": _STR}, ["name"]), _delete_skill, False),
        Tool("admin.create_kb", "Create a new knowledge base.",
             _obj({"name": _STR}, ["name"]), _create_kb, False),
        Tool("admin.write_document",
             "Write generated text into a knowledge base as a document (kb defaults to 'default').",
             _obj({"kb": _STR, "filename": _STR, "text": _STR}, ["text"]), _write_document, False),
        Tool("admin.create_agent", "Build a new agent (or team) from a description.",
             _obj({"request": _STR}, ["request"]), _create_agent, False),
    ]
