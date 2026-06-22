"""photos with moderation status

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "moderation_status",
            sa.Enum("pending", "approved", "rejected", name="moderation_status"),
            nullable=False,
        ),
        sa.Column("nsfw_score", sa.Float(), nullable=True),
        sa.Column("moderation_reason", sa.String(length=255), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_photos_user_id", "photos", ["user_id"])
    op.create_index(
        "ix_photos_moderation_status", "photos", ["moderation_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_photos_moderation_status", table_name="photos")
    op.drop_index("ix_photos_user_id", table_name="photos")
    op.drop_table("photos")
    sa.Enum(name="moderation_status").drop(op.get_bind(), checkfirst=True)
