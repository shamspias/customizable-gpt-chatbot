"""Plugin (MCP connector) management: browse templates, install, configure, test,
enable/disable, and remove. Writes are admin-only (connectors carry credentials)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from veldra_app import plugins, plugins_repo
from veldra_app.auth import Context, get_context, require_role
from veldra_app.db import get_sessionmaker

router = APIRouter(prefix="/api/plugins")

# Built-in tool namespaces a plugin key must not shadow.
_RESERVED = {"kb", "time", "math", "calc", "http", "web", "fs", "json", "regex", "agent"}
_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
_TRANSPORTS = {"http", "sse", "stdio"}

Ctx = Context
Admin = Depends(require_role("admin"))
Any_ = Depends(get_context)


class PluginInstall(BaseModel):
    key: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=400)
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)
    enabled: bool = True


class PluginPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    transport: str | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    headers: dict[str, str] | None = None
    env: dict[str, str] | None = None
    tool_allowlist: list[str] | None = None
    enabled: bool | None = None


class AdHocTest(BaseModel):
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)


def _validate_key(key: str) -> str:
    key = key.strip().lower()
    if not _KEY_RE.match(key):
        raise HTTPException(400, "key must be a slug: lowercase letters, digits, - or _")
    if key in _RESERVED:
        raise HTTPException(400, f"'{key}' is a reserved built-in namespace")
    return key


def _split(transport: str, url: str, command: str, args: list[str],
           headers: dict, env: dict, allowlist: list[str]) -> tuple[dict, dict]:
    """Partition into non-secret `config` and secret `secret`."""
    config = {
        "url": url, "command": command, "args": list(args or []),
        "tool_allowlist": [a for a in (allowlist or []) if a],
        "header_names": sorted(headers.keys()),
    }
    secret = {"headers": dict(headers or {}), "env": dict(env or {})}
    return config, secret


def _public(row: dict) -> dict:
    cfg = row.get("config") or {}
    return {
        "id": str(row["id"]), "key": row["key"], "name": row["name"],
        "description": row.get("description") or "", "kind": row.get("kind") or "mcp",
        "transport": row.get("transport") or "http",
        "url": cfg.get("url", ""), "command": cfg.get("command", ""),
        "args": cfg.get("args") or [], "tool_allowlist": cfg.get("tool_allowlist") or [],
        "header_names": cfg.get("header_names") or [],
        "enabled": bool(row.get("enabled")), "status": row.get("status") or "unknown",
        "status_detail": row.get("status_detail"), "n_tools": row.get("n_tools") or 0,
    }


@router.get("/templates")
async def templates(ctx: Context = Any_) -> list[dict]:
    return plugins.TEMPLATES


@router.get("")
async def list_installed(ctx: Context = Any_) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as db:
        rows = await plugins_repo.list_plugins(db, ctx.tenant_id)
    return [_public(r) for r in rows]


@router.post("")
async def install(req: PluginInstall, ctx: Context = Admin) -> dict:
    key = _validate_key(req.key)
    if req.transport not in _TRANSPORTS:
        raise HTTPException(400, f"transport must be one of {sorted(_TRANSPORTS)}")
    if req.transport in ("http", "sse") and not req.url.strip():
        raise HTTPException(400, "an http/sse connector needs a url")
    if req.transport == "stdio" and not req.command.strip():
        raise HTTPException(400, "a stdio connector needs a command")
    config, secret = _split(
        req.transport, req.url.strip(), req.command.strip(), req.args,
        req.headers, req.env, req.tool_allowlist,
    )
    sm = get_sessionmaker()
    async with sm() as db:
        if await plugins_repo.get_by_key(db, ctx.tenant_id, key):
            raise HTTPException(409, f"a plugin with key '{key}' already exists")
        pid = await plugins_repo.create_plugin(
            db, ctx.tenant_id, key=key, name=req.name.strip(), description=req.description,
            kind="mcp", transport=req.transport, config=config, secret=secret, enabled=req.enabled,
        )
        await db.commit()
        row = await plugins_repo.get_plugin(db, ctx.tenant_id, pid)
    plugins.invalidate_cache(pid)
    return _public(row)


@router.patch("/{plugin_id}")
async def patch(plugin_id: str, req: PluginPatch, ctx: Context = Admin) -> dict:
    sm = get_sessionmaker()
    async with sm() as db:
        cur = await plugins_repo.get_with_secret(db, ctx.tenant_id, plugin_id)
        if not cur:
            raise HTTPException(404, "plugin not found")
        cfg = cur.get("config") or {}
        sec = cur.get("secret") or {}
        fields: dict = {}
        if req.name is not None:
            fields["name"] = req.name.strip()
        if req.description is not None:
            fields["description"] = req.description
        if req.enabled is not None:
            fields["enabled"] = req.enabled
        if req.transport is not None:
            if req.transport not in _TRANSPORTS:
                raise HTTPException(400, f"transport must be one of {sorted(_TRANSPORTS)}")
            fields["transport"] = req.transport
        # connection fields → recompute config/secret, preserving anything not sent
        url = req.url if req.url is not None else cfg.get("url", "")
        command = req.command if req.command is not None else cfg.get("command", "")
        args = req.args if req.args is not None else cfg.get("args", [])
        allow = (req.tool_allowlist if req.tool_allowlist is not None
                 else cfg.get("tool_allowlist", []))
        headers = req.headers if req.headers is not None else sec.get("headers", {})
        env = req.env if req.env is not None else sec.get("env", {})
        new_cfg, new_sec = _split(
            fields.get("transport", cur.get("transport")), url, command, args, headers, env, allow
        )
        fields["config"] = new_cfg
        fields["secret"] = new_sec
        await plugins_repo.update_plugin(db, ctx.tenant_id, plugin_id, **fields)
        await db.commit()
        row = await plugins_repo.get_plugin(db, ctx.tenant_id, plugin_id)
    plugins.invalidate_cache(plugin_id)
    return _public(row)


@router.delete("/{plugin_id}")
async def remove(plugin_id: str, ctx: Context = Admin) -> dict:
    sm = get_sessionmaker()
    async with sm() as db:
        await plugins_repo.delete_plugin(db, ctx.tenant_id, plugin_id)
        await db.commit()
    plugins.invalidate_cache(plugin_id)
    return {"ok": True}


@router.post("/{plugin_id}/test")
async def test_installed(plugin_id: str, ctx: Context = Admin) -> dict:
    sm = get_sessionmaker()
    async with sm() as db:
        row = await plugins_repo.get_with_secret(db, ctx.tenant_id, plugin_id)
        if not row:
            raise HTTPException(404, "plugin not found")
    plugins.invalidate_cache(plugin_id)
    result = await plugins.mcp_provider.probe(plugins.to_server_config(row))
    n = len(result.get("tools") or [])
    async with sm() as db:
        await plugins_repo.set_status(
            db, ctx.tenant_id, plugin_id,
            "ok" if result["ok"] else "error", result.get("error") or None, n,
        )
        await db.commit()
    return {"ok": result["ok"], "error": result.get("error", ""),
            "tools": [{"name": t["name"], "description": t.get("description", "")}
                      for t in result.get("tools", [])]}


@router.post("/test")
async def test_adhoc(req: AdHocTest, ctx: Context = Admin) -> dict:
    """Probe a connector config before saving it."""
    if req.transport in ("http", "sse") and not req.url.strip():
        raise HTTPException(400, "an http/sse connector needs a url")
    if req.transport == "stdio" and not req.command.strip():
        raise HTTPException(400, "a stdio connector needs a command")
    cfg = plugins.to_server_config({
        "transport": req.transport,
        "config": {"url": req.url.strip(), "command": req.command.strip(), "args": req.args},
        "secret": {"headers": req.headers, "env": req.env},
    })
    result = await plugins.mcp_provider.probe(cfg)
    return {"ok": result["ok"], "error": result.get("error", ""),
            "tools": [{"name": t["name"], "description": t.get("description", "")}
                      for t in result.get("tools", [])]}
