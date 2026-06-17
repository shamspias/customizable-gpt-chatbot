"""Async data access for installed plugins (MCP connectors). Mirrors veldra_app.repo."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from veldra_app.models import Plugin
from veldra_app.repo import is_uuid

_COLS = (
    Plugin.id, Plugin.key, Plugin.name, Plugin.description, Plugin.kind, Plugin.transport,
    Plugin.config, Plugin.enabled, Plugin.status, Plugin.status_detail, Plugin.n_tools,
    Plugin.created_at, Plugin.updated_at,
)


async def list_plugins(session: AsyncSession, tenant_id: str) -> list[dict]:
    """All plugins for the workspace (secret omitted — never leaves the server)."""
    res = await session.execute(
        select(*_COLS).where(Plugin.tenant_id == tenant_id).order_by(Plugin.created_at)
    )
    return [dict(r) for r in res.mappings()]


async def list_enabled(session: AsyncSession, tenant_id: str) -> list[dict]:
    """Enabled plugins *with* their secret + config — for building the tool registry."""
    res = await session.execute(
        select(
            Plugin.id, Plugin.key, Plugin.name, Plugin.transport,
            Plugin.config, Plugin.secret, Plugin.updated_at, Plugin.created_at,
        )
        .where(Plugin.tenant_id == tenant_id, Plugin.enabled.is_(True))
        .order_by(Plugin.created_at)
    )
    return [dict(r) for r in res.mappings()]


async def get_plugin(session: AsyncSession, tenant_id: str, plugin_id: str) -> dict | None:
    if not is_uuid(plugin_id):
        return None
    res = await session.execute(
        select(*_COLS).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_with_secret(session: AsyncSession, tenant_id: str, plugin_id: str) -> dict | None:
    if not is_uuid(plugin_id):
        return None
    res = await session.execute(
        select(
            Plugin.id, Plugin.key, Plugin.name, Plugin.transport, Plugin.config, Plugin.secret,
        ).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_by_key(session: AsyncSession, tenant_id: str, key: str) -> dict | None:
    res = await session.execute(
        select(Plugin.id, Plugin.key).where(Plugin.tenant_id == tenant_id, Plugin.key == key)
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def create_plugin(session: AsyncSession, tenant_id: str, **fields: Any) -> str:
    return str(
        await session.scalar(
            insert(Plugin).values(tenant_id=tenant_id, **fields).returning(Plugin.id)
        )
    )


_UPDATABLE = {
    "name", "description", "transport", "config", "secret", "enabled",
    "status", "status_detail", "n_tools",
}


async def update_plugin(
    session: AsyncSession, tenant_id: str, plugin_id: str, **fields: Any
) -> None:
    if not is_uuid(plugin_id):
        return
    allowed = {k: v for k, v in fields.items() if k in _UPDATABLE and v is not None}
    if allowed:
        allowed["updated_at"] = func.now()
        await session.execute(
            update(Plugin)
            .where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
            .values(**allowed)
        )


async def set_status(
    session: AsyncSession, tenant_id: str, plugin_id: str,
    status: str, detail: str | None, n_tools: int,
) -> None:
    await session.execute(
        update(Plugin)
        .where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
        .values(status=status, status_detail=detail, n_tools=n_tools, updated_at=func.now())
    )


async def delete_plugin(session: AsyncSession, tenant_id: str, plugin_id: str) -> None:
    if not is_uuid(plugin_id):
        return
    await session.execute(
        delete(Plugin).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
