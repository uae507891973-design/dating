"""initial schema: users, profiles, consents

Revision ID: 0001
Revises:
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "active", "blocked", "deleted", name="user_status"
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("user", "moderator", "admin", name="user_role"),
            nullable=False,
        ),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(length=80), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.Enum("male", "female", name="gender"), nullable=True),
        sa.Column("looking_for", sa.Enum("male", "female", name="looking_for"), nullable=True),
        sa.Column(
            "intent",
            sa.Enum("marriage", "relationship", "friendship", name="intent"),
            nullable=True,
        ),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("doc_version", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_consents_user_id", "consents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_consents_user_id", table_name="consents")
    op.drop_table("consents")
    op.drop_table("profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
    sa.Enum(name="intent").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="looking_for").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gender").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)
