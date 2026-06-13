"""Async database access + a tiny forward-only SQL migration runner.

    python -m loom_app.db migrate     # apply deploy/migrations/*.sql

We keep raw SQL migrations (not an ORM migration tool) so the schema is readable
and reviewable. The runner substitutes `{{EMBED_DIM}}` with the configured
embedding dimension and records applied files in `schema_migrations`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from loom_app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker | None = None

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "deploy" / "migrations"


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().async_database_url, pool_size=10, max_overflow=20, future=True
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


# ───────────────────────── migrations ─────────────────────────
async def run_migrations() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            print(f"no migrations found in {MIGRATIONS_DIR}")
            return
        for path in files:
            if path.name in applied:
                print(f"  skip  {path.name} (already applied)")
                continue
            sql = path.read_text().replace("{{EMBED_DIM}}", str(settings.embed_dim))
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
                )
            print(f"  apply {path.name}")
        print("migrations up to date.")
    finally:
        await conn.close()


def _main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if cmd == "migrate":
        asyncio.run(run_migrations())
    else:
        print(f"unknown command: {cmd}\nusage: python -m loom_app.db migrate")
        raise SystemExit(2)


if __name__ == "__main__":
    _main()
