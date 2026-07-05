"""profiles.video_calls_enabled; matches.origin

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "video_calls_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "origin", sa.String(length=16), nullable=False, server_default="mutual"
        ),
    )


def downgrade() -> None:
    op.drop_column("matches", "origin")
    op.drop_column("profiles", "video_calls_enabled")
