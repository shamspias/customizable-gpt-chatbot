"""Async data access for identity/access: users, memberships, sessions, invites,
and first-run setup state. Mirrors the style of ``veldra_app.repo`` (2.0 expression
language, dict returns, caller owns the transaction)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from veldra_app.auth import Context, hash_token
from veldra_app.config import DEFAULT_TENANT_ID
from veldra_app.models import Invite, Membership, SetupState, Tenant, User, UserSession
from veldra_app.repo import is_uuid


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ───────────────────────── users ─────────────────────────
async def count_users(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(User.id))) or 0)


async def get_user_by_email(session: AsyncSession, email: str) -> dict | None:
    res = await session.execute(
        select(
            User.id, User.email, User.name, User.password_hash, User.is_active
        ).where(User.email == _norm_email(email))
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_user(session: AsyncSession, user_id: str) -> dict | None:
    if not is_uuid(user_id):
        return None
    res = await session.execute(
        select(User.id, User.email, User.name, User.is_active, User.created_at, User.last_login_at)
        .where(User.id == user_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def create_user(
    session: AsyncSession,
    email: str,
    name: str,
    password_hash: str | None,
    is_active: bool = True,
) -> str:
    return str(
        await session.scalar(
            insert(User)
            .values(
                email=_norm_email(email), name=name.strip(),
                password_hash=password_hash, is_active=is_active,
            )
            .returning(User.id)
        )
    )


async def set_password(session: AsyncSession, user_id: str, password_hash: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )


async def touch_last_login(session: AsyncSession, user_id: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(last_login_at=func.now())
    )


# ───────────────────────── memberships ─────────────────────────
async def create_membership(
    session: AsyncSession, user_id: str, tenant_id: str, role: str
) -> str:
    return str(
        await session.scalar(
            insert(Membership)
            .values(user_id=user_id, tenant_id=tenant_id, role=role)
            .returning(Membership.id)
        )
    )


async def list_members(session: AsyncSession, tenant_id: str) -> list[dict]:
    res = await session.execute(
        select(
            User.id, User.email, User.name, User.is_active,
            User.created_at, User.last_login_at, Membership.role,
        )
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at)
    )
    return [dict(r) for r in res.mappings()]


async def set_member_role(
    session: AsyncSession, user_id: str, tenant_id: str, role: str
) -> None:
    await session.execute(
        update(Membership)
        .where(Membership.user_id == user_id, Membership.tenant_id == tenant_id)
        .values(role=role)
    )


async def count_admins(session: AsyncSession, tenant_id: str) -> int:
    return int(
        await session.scalar(
            select(func.count(Membership.id)).where(
                Membership.tenant_id == tenant_id, Membership.role == "admin"
            )
        )
        or 0
    )


async def remove_member(session: AsyncSession, user_id: str, tenant_id: str) -> None:
    """Remove a user from the workspace; deletes the user entirely if this was their
    only membership (single-workspace product)."""
    await session.execute(
        delete(Membership).where(
            Membership.user_id == user_id, Membership.tenant_id == tenant_id
        )
    )
    remaining = await session.scalar(
        select(func.count(Membership.id)).where(Membership.user_id == user_id)
    )
    if not remaining:
        await session.execute(delete(User).where(User.id == user_id))


# ───────────────────────── sessions ─────────────────────────
async def create_session(
    session: AsyncSession, user_id: str, token_hash: str, ttl_days: int,
    user_agent: str | None = None,
) -> str:
    expires = _utcnow() + timedelta(days=ttl_days)
    return str(
        await session.scalar(
            insert(UserSession)
            .values(
                user_id=user_id, token_hash=token_hash,
                user_agent=(user_agent or "")[:400], expires_at=expires,
            )
            .returning(UserSession.id)
        )
    )


async def resolve_session(session: AsyncSession, token: str) -> Context | None:
    """Resolve a bearer token to a Context (active session + user + membership)."""
    th = hash_token(token)
    res = await session.execute(
        select(
            UserSession.id, User.id.label("user_id"), User.email, User.name,
            Membership.role, Membership.tenant_id,
        )
        .join(User, User.id == UserSession.user_id)
        .join(Membership, Membership.user_id == User.id)
        .where(
            UserSession.token_hash == th,
            UserSession.expires_at > func.now(),
            User.is_active.is_(True),
        )
        .order_by(Membership.created_at)
        .limit(1)
    )
    row = res.mappings().first()
    if row is None:
        return None
    await session.execute(
        update(UserSession).where(UserSession.id == row["id"]).values(last_seen_at=func.now())
    )
    return Context(
        tenant_id=str(row["tenant_id"]), user_id=str(row["user_id"]),
        role=row["role"], email=row["email"], name=row["name"] or row["email"],
        authenticated=True,
    )


async def revoke_session(session: AsyncSession, token: str) -> None:
    await session.execute(
        delete(UserSession).where(UserSession.token_hash == hash_token(token))
    )


async def revoke_user_sessions(session: AsyncSession, user_id: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.user_id == user_id))


# ───────────────────────── tenant / setup state ─────────────────────────
async def get_tenant(session: AsyncSession, tenant_id: str) -> dict | None:
    res = await session.execute(
        select(Tenant.id, Tenant.slug, Tenant.name).where(Tenant.id == tenant_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def rename_tenant(session: AsyncSession, tenant_id: str, name: str) -> None:
    name = (name or "").strip()
    if name:
        await session.execute(update(Tenant).where(Tenant.id == tenant_id).values(name=name))


async def get_setup_state(session: AsyncSession, tenant_id: str) -> dict:
    res = await session.execute(
        select(SetupState.completed, SetupState.current_step, SetupState.data)
        .where(SetupState.tenant_id == tenant_id)
    )
    row = res.mappings().first()
    return dict(row) if row else {"completed": False, "current_step": "welcome", "data": {}}


async def upsert_setup_state(
    session: AsyncSession, tenant_id: str, *, completed: bool | None = None,
    current_step: str | None = None, data: dict | None = None,
) -> None:
    existing = await session.scalar(
        select(SetupState.id).where(SetupState.tenant_id == tenant_id)
    )
    values: dict[str, Any] = {"updated_at": func.now()}
    if completed is not None:
        values["completed"] = completed
    if current_step is not None:
        values["current_step"] = current_step
    if data is not None:
        values["data"] = data
    if existing:
        await session.execute(
            update(SetupState).where(SetupState.tenant_id == tenant_id).values(**values)
        )
    else:
        await session.execute(insert(SetupState).values(tenant_id=tenant_id, **values))


# ───────────────────────── invites ─────────────────────────
async def create_invite(
    session: AsyncSession, tenant_id: str, email: str, role: str,
    token_hash: str, invited_by: str | None, ttl_days: int,
) -> str:
    # Replace any prior pending invite for the same email so links stay unambiguous.
    await session.execute(
        delete(Invite).where(
            Invite.tenant_id == tenant_id,
            Invite.email == _norm_email(email),
            Invite.accepted_at.is_(None),
        )
    )
    expires = _utcnow() + timedelta(days=ttl_days)
    return str(
        await session.scalar(
            insert(Invite)
            .values(
                tenant_id=tenant_id, email=_norm_email(email), role=role,
                token_hash=token_hash, invited_by=invited_by, expires_at=expires,
            )
            .returning(Invite.id)
        )
    )


async def list_invites(session: AsyncSession, tenant_id: str) -> list[dict]:
    res = await session.execute(
        select(
            Invite.id, Invite.email, Invite.role, Invite.created_at,
            Invite.expires_at, Invite.accepted_at,
        )
        .where(Invite.tenant_id == tenant_id, Invite.accepted_at.is_(None))
        .order_by(Invite.created_at.desc())
    )
    return [dict(r) for r in res.mappings()]


async def get_invite_by_token(session: AsyncSession, token: str) -> dict | None:
    res = await session.execute(
        select(
            Invite.id, Invite.tenant_id, Invite.email, Invite.role, Invite.expires_at,
        )
        .where(
            Invite.token_hash == hash_token(token),
            Invite.accepted_at.is_(None),
            Invite.expires_at > func.now(),
        )
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def mark_invite_accepted(session: AsyncSession, invite_id: str) -> None:
    await session.execute(
        update(Invite).where(Invite.id == invite_id).values(accepted_at=func.now())
    )


async def delete_invite(session: AsyncSession, tenant_id: str, invite_id: str) -> None:
    if not is_uuid(invite_id):
        return
    await session.execute(
        delete(Invite).where(Invite.id == invite_id, Invite.tenant_id == tenant_id)
    )


# Re-export for convenience.
DEFAULT_TENANT = DEFAULT_TENANT_ID
