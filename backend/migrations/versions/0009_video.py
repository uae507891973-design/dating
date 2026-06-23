"""video sessions

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "initiator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "requested", "active", "ended", "declined", name="video_status"
            ),
            nullable=False,
        ),
        sa.Column("blur_level", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("continue_initiator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("continue_partner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_video_sessions_match_id", "video_sessions", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_video_sessions_match_id", table_name="video_sessions")
    op.drop_table("video_sessions")
    sa.Enum(name="video_status").drop(op.get_bind(), checkfirst=True)
