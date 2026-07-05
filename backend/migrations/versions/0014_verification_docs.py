"""verification selfie/document paths; message_status 'delivered'

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "verifications",
        sa.Column("selfie_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "verifications",
        sa.Column("document_path", sa.String(length=512), nullable=True),
    )
    # Новый статус доставки сообщений.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE message_status ADD VALUE IF NOT EXISTS 'delivered'"
        )


def downgrade() -> None:
    op.drop_column("verifications", "document_path")
    op.drop_column("verifications", "selfie_path")
    # Удаление значения из enum в PostgreSQL не поддерживается.
