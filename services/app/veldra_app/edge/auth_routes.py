"""Auth + first-run setup endpoints.

* ``/api/setup/*`` — the install wizard (open until a workspace has its first admin).
* ``/api/auth/*``  — login / logout / me / team management / invite acceptance.

These are mounted alongside the main edge router but kept separate so the keystone
``get_context`` dependency (which they partly bypass) stays easy to reason about.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from veldra_app import auth, auth_repo
from veldra_app.auth import Context, get_context, require_role
from veldra_app.config import DEFAULT_TENANT_ID, get_settings
from veldra_app.db import get_sessionmaker

router = APIRouter(prefix="/api")

ROLES = {"admin", "member", "viewer"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_email(v: str) -> str:
    v = (v or "").strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


# ───────────────────────── schemas ─────────────────────────
class _EmailModel(BaseModel):
    email: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _check_email(v)


class SetupCompleteRequest(_EmailModel):
    workspace_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(_EmailModel):
    password: str = Field(min_length=1, max_length=200)


class InviteRequest(_EmailModel):
    role: str = Field(default="member")


class AcceptRequest(BaseModel):
    token: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class RoleRequest(BaseModel):
    role: str


def _user_public(user_id: str, email: str, name: str, role: str) -> dict:
    return {"id": user_id, "email": email, "name": name, "role": role}


# ───────────────────────── setup (install wizard) ─────────────────────────
@router.get("/setup/status")
async def setup_status() -> dict:
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        n_users = await auth_repo.count_users(db)
        state = await auth_repo.get_setup_state(db, DEFAULT_TENANT_ID)
        tenant = await auth_repo.get_tenant(db, DEFAULT_TENANT_ID)
    needs_setup = bool(s.auth_enabled and n_users == 0 and not state.get("completed"))
    return {
        "needs_setup": needs_setup,
        "completed": bool(state.get("completed")) or n_users > 0,
        "auth_enabled": s.auth_enabled,
        "has_users": n_users > 0,
        "workspace_name": (tenant or {}).get("name") or "Veldra",
        "llm_provider": s.llm_provider,
        "embed_provider": s.embed_provider,
        "embed_dim": s.embed_dim,
    }


@router.post("/setup/test")
async def setup_test() -> dict:
    """Live-check the configured LLM + embedding providers so the admin sees a green
    light before finishing setup. Best-effort: any failure is reported, never raised."""
    out: dict = {"llm_ok": False, "llm_detail": "", "embed_ok": False, "embed_detail": ""}

    from veldra_llm import embed_query, get_provider

    from veldra_app.rag.ingest import embed_config

    try:
        provider = get_provider()
        data = await provider.parse_json(
            model=provider.resolve(None),
            system="You are a health check. Reply with the requested JSON only.",
            messages=[{"role": "user", "content": 'Return {"ok": true}.'}],
            schema={
                "type": "object", "additionalProperties": False,
                "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
            },
            max_tokens=64,
        )
        out["llm_ok"] = bool(data is not None)
        out["llm_detail"] = "Reachable" if data is not None else "No response"
    except Exception as exc:  # noqa: BLE001 — surfaced to the UI
        out["llm_detail"] = str(exc)[:300]

    try:
        cfg = embed_config()
        vec = await embed_query("ping", cfg)
        out["embed_ok"] = len(vec) == cfg.dim
        out["embed_detail"] = (
            f"{cfg.resolved_provider()} · {len(vec)} dims"
            if out["embed_ok"]
            else f"dimension mismatch: got {len(vec)}, expected {cfg.dim}"
        )
    except Exception as exc:  # noqa: BLE001
        out["embed_detail"] = str(exc)[:300]

    return out


@router.post("/setup/complete")
async def setup_complete(req: SetupCompleteRequest, request: Request) -> dict:
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        if await auth_repo.count_users(db) > 0:
            raise HTTPException(409, "Setup already completed — sign in instead.")
        try:
            pw_hash = auth.hash_password(req.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        user_id = await auth_repo.create_user(db, req.email, req.name, pw_hash)
        await auth_repo.create_membership(db, user_id, DEFAULT_TENANT_ID, "admin")
        await auth_repo.rename_tenant(db, DEFAULT_TENANT_ID, req.workspace_name)
        await auth_repo.upsert_setup_state(
            db, DEFAULT_TENANT_ID, completed=True, current_step="done"
        )
        token, token_hash = auth.new_session_token()
        await auth_repo.create_session(
            db, user_id, token_hash, s.session_ttl_days,
            user_agent=request.headers.get("user-agent"),
        )
        await auth_repo.touch_last_login(db, user_id)
        await db.commit()
    return {
        "token": token,
        "user": _user_public(user_id, req.email.lower(), req.name, "admin"),
        "workspace_name": req.workspace_name,
    }


# ───────────────────────── auth ─────────────────────────
@router.post("/auth/login")
async def login(req: LoginRequest, request: Request) -> dict:
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        user = await auth_repo.get_user_by_email(db, req.email)
        if not user or not user.get("is_active") or not auth.verify_password(
            req.password, user.get("password_hash")
        ):
            raise HTTPException(401, "Invalid email or password")
        members = await auth_repo.list_members(db, DEFAULT_TENANT_ID)
        role = next((m["role"] for m in members if str(m["id"]) == str(user["id"])), "member")
        token, token_hash = auth.new_session_token()
        await auth_repo.create_session(
            db, str(user["id"]), token_hash, s.session_ttl_days,
            user_agent=request.headers.get("user-agent"),
        )
        await auth_repo.touch_last_login(db, str(user["id"]))
        await db.commit()
    return {
        "token": token,
        "user": _user_public(str(user["id"]), user["email"], user["name"], role),
    }


@router.post("/auth/logout")
async def logout(request: Request, ctx: Context = Depends(get_context)) -> dict:
    token = auth.bearer_token(request)
    if token:
        sm = get_sessionmaker()
        async with sm() as db:
            await auth_repo.revoke_session(db, token)
            await db.commit()
    return {"ok": True}


@router.get("/auth/me")
async def me(ctx: Context = Depends(get_context)) -> dict:
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        tenant = await auth_repo.get_tenant(db, ctx.tenant_id)
    return {
        "authenticated": ctx.authenticated,
        "auth_enabled": s.auth_enabled,
        "user": _user_public(ctx.user_id or "system", ctx.email, ctx.name, ctx.role),
        "workspace": {"id": ctx.tenant_id, "name": (tenant or {}).get("name") or "Veldra"},
    }


# ───────────────────────── team management (admin) ─────────────────────────
@router.get("/auth/users")
async def list_users(ctx: Context = Depends(require_role("admin"))) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as db:
        return await auth_repo.list_members(db, ctx.tenant_id)


@router.post("/auth/invites")
async def create_invite(req: InviteRequest, request: Request,
                        ctx: Context = Depends(require_role("admin"))) -> dict:
    if req.role not in ROLES:
        raise HTTPException(400, f"role must be one of {sorted(ROLES)}")
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        if await auth_repo.get_user_by_email(db, req.email):
            raise HTTPException(409, "A user with that email already exists.")
        token, token_hash = auth.new_session_token()
        invite_id = await auth_repo.create_invite(
            db, ctx.tenant_id, req.email, req.role, token_hash, ctx.user_id, s.invite_ttl_days
        )
        await db.commit()
    base = s.api_base_url.rstrip("/")
    return {
        "id": invite_id,
        "email": req.email.lower(),
        "role": req.role,
        "token": token,
        "accept_url": f"{base}/#/accept/{token}",
    }


@router.get("/auth/invites")
async def list_invites(ctx: Context = Depends(require_role("admin"))) -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as db:
        return await auth_repo.list_invites(db, ctx.tenant_id)


@router.delete("/auth/invites/{invite_id}")
async def delete_invite(invite_id: str, ctx: Context = Depends(require_role("admin"))) -> dict:
    sm = get_sessionmaker()
    async with sm() as db:
        await auth_repo.delete_invite(db, ctx.tenant_id, invite_id)
        await db.commit()
    return {"ok": True}


@router.get("/auth/invites/{token}/preview")
async def preview_invite(token: str) -> dict:
    sm = get_sessionmaker()
    async with sm() as db:
        invite = await auth_repo.get_invite_by_token(db, token)
        if not invite:
            raise HTTPException(404, "This invite is invalid or has expired.")
        tenant = await auth_repo.get_tenant(db, invite["tenant_id"])
    return {
        "email": invite["email"],
        "role": invite["role"],
        "workspace_name": (tenant or {}).get("name") or "Veldra",
    }


@router.post("/auth/accept")
async def accept_invite(req: AcceptRequest, request: Request) -> dict:
    s = get_settings()
    sm = get_sessionmaker()
    async with sm() as db:
        invite = await auth_repo.get_invite_by_token(db, req.token)
        if not invite:
            raise HTTPException(404, "This invite is invalid or has expired.")
        if await auth_repo.get_user_by_email(db, invite["email"]):
            raise HTTPException(409, "A user with that email already exists.")
        try:
            pw_hash = auth.hash_password(req.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        user_id = await auth_repo.create_user(db, invite["email"], req.name, pw_hash)
        await auth_repo.create_membership(db, user_id, invite["tenant_id"], invite["role"])
        await auth_repo.mark_invite_accepted(db, invite["id"])
        token, token_hash = auth.new_session_token()
        await auth_repo.create_session(
            db, user_id, token_hash, s.session_ttl_days,
            user_agent=request.headers.get("user-agent"),
        )
        await auth_repo.touch_last_login(db, user_id)
        await db.commit()
    return {
        "token": token,
        "user": _user_public(user_id, invite["email"], req.name, invite["role"]),
    }


@router.put("/auth/users/{user_id}/role")
async def set_user_role(user_id: str, req: RoleRequest,
                       ctx: Context = Depends(require_role("admin"))) -> dict:
    if req.role not in ROLES:
        raise HTTPException(400, f"role must be one of {sorted(ROLES)}")
    sm = get_sessionmaker()
    async with sm() as db:
        # Never let the last admin demote themselves out of the workspace.
        if req.role != "admin" and str(user_id) == str(ctx.user_id):
            if await auth_repo.count_admins(db, ctx.tenant_id) <= 1:
                raise HTTPException(400, "You are the only admin — promote someone first.")
        await auth_repo.set_member_role(db, user_id, ctx.tenant_id, req.role)
        await db.commit()
    return {"ok": True, "role": req.role}


@router.delete("/auth/users/{user_id}")
async def remove_user(user_id: str, ctx: Context = Depends(require_role("admin"))) -> dict:
    if str(user_id) == str(ctx.user_id):
        raise HTTPException(400, "You can't remove yourself — sign out instead.")
    sm = get_sessionmaker()
    async with sm() as db:
        await auth_repo.revoke_user_sessions(db, user_id)
        await auth_repo.remove_member(db, user_id, ctx.tenant_id)
        await db.commit()
    return {"ok": True}
