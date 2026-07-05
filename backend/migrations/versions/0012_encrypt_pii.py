"""widen users.phone/email for encrypted PII

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Шифртекст (base64 AES-SIV) длиннее исходных значений — расширяем колонки.
    op.alter_column("users", "phone", type_=sa.String(length=255))
    op.alter_column("users", "email", type_=sa.String(length=512))


def downgrade() -> None:
    op.alter_column("users", "phone", type_=sa.String(length=32))
    op.alter_column("users", "email", type_=sa.String(length=255))
