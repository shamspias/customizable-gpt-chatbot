"""SQLAlchemy ORM models — the schema source of truth.

An agent is *data*: a stable `agents` row + an append-only stack of immutable
`agent_specs` versions. RAG lives in `knowledge_bases` → `documents` →
(`page_index`, `chunks`); `chunks` carries the dual representation used by hybrid
retrieval — a pgvector `embedding` and a generated `tsv` (Postgres FTS) column.
Runs + run_steps are the append-only execution/checkpoint log.

These models *are* the schema: Alembic autogenerates migrations by diffing the
database against `Base.metadata` (see `deploy/alembic/`). Multi-tenancy: every
tenant-scoped table carries `tenant_id`; RLS policies are defined in the initial
migration (not enabled in the MVP — a v1 task).
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from veldra_app.config import get_settings

# Embedding dimension is fixed at first migration (768 = nomic-embed-text,
# 1536 = text-embedding-3-small). Changing it requires a re-embed migration.
EMBED_DIM = get_settings().embed_dim

# Deterministic constraint/index names → clean Alembic autogenerate diffs.
NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Reusable column factories (server-side defaults so raw SQL/other clients agree).
def _pk() -> Mapped[str]:
    return mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ───────────────────────── tenancy ─────────────────────────
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = _pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (UniqueConstraint("slug", name="tenants_slug_key"),)


# ───────────────────────── agents (versioned spec) ─────────────────────────
class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("agents_tenant_name_idx", "tenant_id", "name", unique=True),)


class SpecVersion(Base):
    """An immutable AgentSpec version. Rollback = repoint Agent.current_version."""

    __tablename__ = "agent_specs"

    id: Mapped[str] = _pk()
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)  # e.g. the self-mod request that produced it
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="agent_specs_agent_id_version_key"),
    )


# ───────────────────────── knowledge bases ─────────────────────────
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Retrieval config (per-KB): how queries are answered.
    retrieval_mode: Mapped[str] = mapped_column(  # hybrid | semantic | keyword
        Text, nullable=False, server_default=text("'hybrid'")
    )
    embedding_model: Mapped[str | None] = mapped_column(Text)  # "provider:model" or null = global
    rerank_model: Mapped[str | None] = mapped_column(Text)  # "provider:model" or null = none
    vector_store: Mapped[str] = mapped_column(  # pgvector | qdrant
        Text, nullable=False, server_default=text("'pgvector'")
    )
    page_index_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = _pk()
    kb_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)  # faithful editable source
    num_pages: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(  # pending|ingesting|ready|failed
        Text, nullable=False, server_default=text("'pending'")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class PageIndex(Base):
    """Document structure tree (pages/sections) — powers citation labels and,
    later, parent-document expansion. Self-referential via parent_id."""

    __tablename__ = "page_index"

    id: Mapped[str] = _pk()
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("page_index.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'page' | 'section'
    label: Mapped[str | None] = mapped_column(Text)  # section title / "Page N"
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)  # e.g. "2 › Pricing › Tiers"
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("page_index_doc_idx", "document_id"),)


class Chunk(Base):
    """Retrievable chunk with citation metadata + dual representation: a pgvector
    `embedding` (ANN via HNSW) and a generated `tsv` (lexical FTS via GIN)."""

    __tablename__ = "chunks"

    id: Mapped[str] = _pk()
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)
    )

    __table_args__ = (
        Index("chunks_kb_idx", "kb_id"),
        Index("chunks_tsv_idx", "tsv", postgresql_using="gin"),
        Index(
            "chunks_vec_idx", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ───────────────────────── runs + event log (checkpoints) ─────────────────────────
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("agents.id"))
    agent_version: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # build | ask | selfmod
    status: Mapped[str] = mapped_column(  # running|done|error|needs_input
        Text, nullable=False, server_default=text("'running'")
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    reward: Mapped[float | None] = mapped_column(Float)  # -1..1 feedback signal
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "runs_idem_idx", "tenant_id", "idempotency_key",
            unique=True, postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class RunStep(Base):
    """Append-only node/turn/tool step — the checkpoint/replay/audit substrate."""

    __tablename__ = "run_steps"

    id: Mapped[str] = _pk()
    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # node|llm_turn|tool_call|...
    name: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("run_steps_run_idx", "run_id", "ordinal"),)


class Audit(Base):
    __tablename__ = "audit"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)  # 'user' | 'orchestrator'
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("audit_tenant_idx", "tenant_id", "created_at"),)


class Skill(Base):
    """A reusable, editable Markdown 'skill' (a focused how-to / playbook). Agents
    list skills by name; the runtime injects the skill's content into the agent's
    system prompt so it can follow the procedure (à la Claude/Hermes skills)."""

    __tablename__ = "skills"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        Index("skills_tenant_name_idx", "tenant_id", "name", unique=True),
    )


class Lesson(Base):
    """Episodic memory: a concrete lesson an agent learned from a past run, injected
    into its system prompt at runtime so it stops repeating mistakes (Reflexion)."""

    __tablename__ = "lessons"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_run_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("lessons_agent_idx", "agent_id", "created_at"),)


# ───────────────────────── identity / access (multi-user) ─────────────────────────
class User(Base):
    """A person who signs in. Global identity; workspace access is via Membership.
    Passwords are stored as a salted PBKDF2-SHA256 digest (see veldra_app.auth)."""

    __tablename__ = "users"

    id: Mapped[str] = _pk()
    email: Mapped[str] = mapped_column(Text, nullable=False)  # stored lower-cased
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    password_hash: Mapped[str | None] = mapped_column(Text)  # null until an invite is accepted
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)


class Membership(Base):
    """Links a user to a workspace (tenant) with a role. One row per (user, tenant);
    in the single-workspace product everyone joins the default tenant."""

    __tablename__ = "memberships"

    id: Mapped[str] = _pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(  # admin | member | viewer
        Text, nullable=False, server_default=text("'member'")
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_id"),
        Index("memberships_tenant_idx", "tenant_id"),
    )


class UserSession(Base):
    """A login session — an opaque bearer token stored only as its SHA-256 hash, so a
    DB leak can't be replayed. Revocable (delete the row) and expiring."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = _pk()
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        Index("user_sessions_user_idx", "user_id"),
    )


class Invite(Base):
    """A pending workspace invitation. The admin shares the token; the invitee sets a
    password to accept, which creates their User + Membership."""

    __tablename__ = "invites"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)  # stored lower-cased
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'member'"))
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_invites_token_hash"),
        Index("invites_tenant_email_idx", "tenant_id", "email"),
    )


class SetupState(Base):
    """First-run setup progress for a workspace. One row per tenant; `completed`
    gates the install wizard so it never reappears once finished."""

    __tablename__ = "setup_state"

    id: Mapped[str] = _pk()
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    current_step: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'welcome'")
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("tenant_id", name="uq_setup_state_tenant_id"),)


__all__ = [
    "Base", "EMBED_DIM",
    "Tenant", "Agent", "SpecVersion", "KnowledgeBase", "Document",
    "PageIndex", "Chunk", "Run", "RunStep", "Audit", "Lesson", "Skill",
    "User", "Membership", "UserSession", "Invite", "SetupState",
]
