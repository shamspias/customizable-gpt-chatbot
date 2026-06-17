"""plugins: installable MCP connectors per workspace

Adds the `plugins` table — tenant-scoped MCP connectors (Streamable HTTP / SSE /
stdio) that contribute tools to a workspace. Built-in tools stay in code; this is
for installable extensions (calculator/web-scraper ship as built-ins, Alibaba and
Shopify as configurable MCP connectors).

Revision ID: b2c3d4e5f6a7
Revises: a1f2c3d4e5f6
Create Date: 2026-06-17 00:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1f2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = sa.UUID(as_uuid=False)


def upgrade() -> None:
    op.create_table(
        "plugins",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'mcp'"), nullable=False),
        sa.Column("transport", sa.Text(), server_default=sa.text("'http'"), nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column("secret", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("n_tools", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("plugins_tenant_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("plugins_pkey")),
        sa.UniqueConstraint("tenant_id", "key", name="uq_plugins_tenant_id"),
    )
    op.create_index("plugins_tenant_idx", "plugins", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("plugins_tenant_idx", table_name="plugins")
    op.drop_table("plugins")
