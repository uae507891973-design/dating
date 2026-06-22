"""antifraud: users.trust_score, risk_flags

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "trust_score", sa.Integer(), nullable=False, server_default="100"
        ),
    )
    op.create_table(
        "risk_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("open", "resolved", name="flag_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_flags_user_id", "risk_flags", ["user_id"])
    op.create_index("ix_risk_flags_status", "risk_flags", ["status"])


def downgrade() -> None:
    op.drop_index("ix_risk_flags_status", table_name="risk_flags")
    op.drop_index("ix_risk_flags_user_id", table_name="risk_flags")
    op.drop_table("risk_flags")
    op.drop_column("users", "trust_score")
    sa.Enum(name="flag_status").drop(op.get_bind(), checkfirst=True)
