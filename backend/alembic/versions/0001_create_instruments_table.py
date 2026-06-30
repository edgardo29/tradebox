"""Create instruments table.

Revision ID: 0001_instruments_table
Revises:
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_instruments_table"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column(
            "currency", sa.String(length=16), server_default=sa.text("'USD'"), nullable=False
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'America/New_York'"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_class IN ('equity', 'etf', 'future', 'crypto', 'forex', 'index', 'other')",
            name="ck_instruments_asset_class_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("symbol", name="uq_instruments_symbol"),
    )
    op.create_index("ix_instruments_asset_class", "instruments", ["asset_class"])
    op.create_index("ix_instruments_is_active", "instruments", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_instruments_is_active", table_name="instruments")
    op.drop_index("ix_instruments_asset_class", table_name="instruments")
    op.drop_table("instruments")
