"""Async database engine/session + the Alembic-backed migration runner.

    python -m veldra_app.db migrate     # = alembic upgrade head (idempotent)

Schema is defined as SQLAlchemy ORM models (`veldra_app.models`) and versioned
with Alembic (`deploy/alembic/`). `run_migrations()` keeps the same one-command
entrypoint the Docker image / Taskfile call on boot, and transparently adopts a
database that was created by the legacy raw-SQL runner (stamp, don't re-create).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from veldra_app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker | None = None

# repo root holds alembic.ini; the script tree lives under deploy/alembic.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"
_ALEMBIC_DIR = _REPO_ROOT / "deploy" / "alembic"


def _json_serializer(obj: object) -> str:
    # default=str so JSONB columns tolerate datetimes/UUIDs in run-step payloads.
    return json.dumps(obj, default=str)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().async_database_url,
            pool_size=10,
            max_overflow=20,
            future=True,
            json_serializer=_json_serializer,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


# ───────────────────────── migrations (Alembic) ─────────────────────────
def alembic_config() -> Config:
    cfg = Config(str(_ALEMBIC_INI)) if _ALEMBIC_INI.exists() else Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", get_settings().async_database_url)
    return cfg


async def _inspect_db() -> tuple[bool, bool]:
    """Return (alembic_managed, has_legacy_schema) without touching the app engine."""
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        managed = await conn.fetchval("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        legacy = await conn.fetchval("SELECT to_regclass('public.agents') IS NOT NULL")
        return bool(managed), bool(legacy)
    finally:
        await conn.close()


async def _drop_legacy_tracking() -> None:
    """Remove the obsolete raw-SQL migration ledger once Alembic owns the schema."""
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute("DROP TABLE IF EXISTS schema_migrations")
    finally:
        await conn.close()


def run_migrations() -> None:
    """Apply migrations up to head. Synchronous: Alembic's env runs its own loop."""
    alembic_managed, has_legacy = asyncio.run(_inspect_db())
    cfg = alembic_config()
    if has_legacy and not alembic_managed:
        # DB predates Alembic (legacy raw-SQL schema) — adopt it without re-creating.
        command.stamp(cfg, "head")
        asyncio.run(_drop_legacy_tracking())
        print("  legacy schema detected → stamped Alembic baseline (no DDL run)")
    command.upgrade(cfg, "head")
    print("migrations up to date.")


def _main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if cmd == "migrate":
        run_migrations()
    else:
        print(f"unknown command: {cmd}\nusage: python -m veldra_app.db migrate")
        raise SystemExit(2)


if __name__ == "__main__":
    _main()
