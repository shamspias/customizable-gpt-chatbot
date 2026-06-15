"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-14

Baseline schema (was deploy/migrations/0001_init.sql). Mirrors veldra_app.models.
The embedding dimension is read from settings at migration time (768 nomic /
1536 text-embedding-3-small). RLS policies are DEFINED but not ENABLED (v1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from veldra_app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_DIM = get_settings().embed_dim

_UUID = postgresql.UUID(as_uuid=False)
_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# Tenant-scoped tables get an (inert) RLS isolation policy, activated in v1.
_RLS_TABLES = ["agents", "knowledge_bases", "documents", "chunks", "runs", "audit"]


def _id() -> sa.Column:
    return sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.text("now()"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        _id(),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("slug", name="tenants_slug_key"),
    )

    op.create_table(
        "agents",
        _id(),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        _created_at(),
    )
    op.create_index("agents_tenant_name_idx", "agents", ["tenant_id", "name"], unique=True)

    op.create_table(
        "agent_specs",
        _id(),
        sa.Column("agent_id", _UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text()),
        _created_at(),
        sa.UniqueConstraint("agent_id", "version", name="agent_specs_agent_id_version_key"),
    )

    op.create_table(
        "knowledge_bases",
        _id(),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created_at(),
    )

    op.create_table(
        "documents",
        _id(),
        sa.Column("kb_id", _UUID, sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text()),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("num_pages", sa.Integer()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error", sa.Text()),
        _created_at(),
    )

    op.create_table(
        "page_index",
        _id(),
        sa.Column("document_id", _UUID, sa.ForeignKey("documents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("parent_id", _UUID, sa.ForeignKey("page_index.id", ondelete="CASCADE")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section_path", sa.Text()),
        sa.Column("char_start", sa.Integer()),
        sa.Column("char_end", sa.Integer()),
    )
    op.create_index("page_index_doc_idx", "page_index", ["document_id"])

    op.create_table(
        "chunks",
        _id(),
        sa.Column("document_id", _UUID, sa.ForeignKey("documents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kb_id", _UUID, sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section_path", sa.Text()),
        sa.Column("char_start", sa.Integer()),
        sa.Column("char_end", sa.Integer()),
        sa.Column("token_count", sa.Integer()),
        sa.Column("embedding", Vector(EMBED_DIM)),
        sa.Column("tsv", postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', content)", persisted=True)),
    )
    op.create_index("chunks_kb_idx", "chunks", ["kb_id"])
    op.create_index("chunks_tsv_idx", "chunks", ["tsv"], postgresql_using="gin")
    op.create_index("chunks_vec_idx", "chunks", ["embedding"], postgresql_using="hnsw",
                    postgresql_ops={"embedding": "vector_cosine_ops"})

    op.create_table(
        "runs",
        _id(),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("agent_id", _UUID, sa.ForeignKey("agents.id")),
        sa.Column("agent_version", sa.Integer()),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("input", postgresql.JSONB()),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        _created_at(),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("runs_idem_idx", "runs", ["tenant_id", "idempotency_key"], unique=True,
                    postgresql_where=sa.text("idempotency_key IS NOT NULL"))

    op.create_table(
        "run_steps",
        _id(),
        sa.Column("run_id", _UUID, sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        _created_at(),
    )
    op.create_index("run_steps_run_idx", "run_steps", ["run_id", "ordinal"])

    op.create_table(
        "audit",
        _id(),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text()),
        sa.Column("target_id", sa.Text()),
        sa.Column("detail", postgresql.JSONB()),
        _created_at(),
    )
    op.create_index("audit_tenant_idx", "audit", ["tenant_id", "created_at"])

    # Deterministic default tenant for the single-tenant MVP.
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, slug, name) VALUES (CAST(:id AS uuid), 'default', 'Default') "
            "ON CONFLICT (slug) DO NOTHING"
        ).bindparams(id=_TENANT_ID)
    )

    # RLS policies (DEFINED, not ENABLED — activated in v1 with a per-request GUC).
    for table in _RLS_TABLES:
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid)"
        )


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in (
        "audit", "run_steps", "runs", "chunks", "page_index",
        "documents", "knowledge_bases", "agent_specs", "agents", "tenants",
    ):
        op.drop_table(table)
