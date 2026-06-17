"""auth: users, memberships, sessions, invites, setup_state

Adds the multi-user / single-workspace identity layer: people sign in (users),
join the workspace with a role (memberships), hold revocable sessions
(user_sessions), can be invited (invites), and the workspace tracks first-run
install progress (setup_state).

Revision ID: a1f2c3d4e5f6
Revises: b3fb5b4b02f0
Create Date: 2026-06-17 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1f2c3d4e5f6"
down_revision: str | None = "b3fb5b4b02f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = sa.UUID(as_uuid=False)


def _id() -> sa.Column:
    return sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at(),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("users_pkey")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "memberships",
        _id(),
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'member'"), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("memberships_user_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("memberships_tenant_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("memberships_pkey")),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_id"),
    )
    op.create_index("memberships_tenant_idx", "memberships", ["tenant_id"], unique=False)

    op.create_table(
        "user_sessions",
        _id(),
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("user_sessions_user_id_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("user_sessions_pkey")),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("user_sessions_user_idx", "user_sessions", ["user_id"], unique=False)

    op.create_table(
        "invites",
        _id(),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'member'"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("invited_by", _UUID, nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("invites_tenant_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"], name=op.f("invites_invited_by_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("invites_pkey")),
        sa.UniqueConstraint("token_hash", name="uq_invites_token_hash"),
    )
    op.create_index("invites_tenant_email_idx", "invites", ["tenant_id", "email"], unique=False)

    op.create_table(
        "setup_state",
        _id(),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "current_step", sa.Text(), server_default=sa.text("'welcome'"), nullable=False
        ),
        sa.Column(
            "data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("setup_state_tenant_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("setup_state_pkey")),
        sa.UniqueConstraint("tenant_id", name="uq_setup_state_tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("setup_state")
    op.drop_index("invites_tenant_email_idx", table_name="invites")
    op.drop_table("invites")
    op.drop_index("user_sessions_user_idx", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("memberships_tenant_idx", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
