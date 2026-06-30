"""Create detected setups table.

Revision ID: 0005_detected_setups_table
Revises: 0004_backtest_runs_table
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_detected_setups_table"
down_revision: str | None = "0004_backtest_runs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detected_setups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backtest_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_partition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("setup_key", sa.String(length=128), nullable=False),
        sa.Column(
            "setup_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("setup_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("setup_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("stop_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("invalidation_price", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "setup_metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
            "setup_status IN ('pending_entry', 'triggered', 'expired', 'filtered_out', "
            "'invalidated', 'detected', 'rejected', 'skipped')",
            name="ck_detected_setups_setup_status_allowed",
        ),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_detected_setups_side_allowed"),
        sa.CheckConstraint(
            "timeframe IN ('1m', '5m')", name="ck_detected_setups_timeframe_allowed"
        ),
        sa.CheckConstraint(
            "entry_price IS NULL OR entry_price > 0", name="ck_detected_setups_entry_price_positive"
        ),
        sa.CheckConstraint(
            "stop_price IS NULL OR stop_price > 0", name="ck_detected_setups_stop_price_positive"
        ),
        sa.CheckConstraint(
            "target_price IS NULL OR target_price > 0",
            name="ck_detected_setups_target_price_positive",
        ),
        sa.CheckConstraint(
            "invalidation_price IS NULL OR invalidation_price > 0",
            name="ck_detected_setups_invalidation_price_positive",
        ),
        sa.ForeignKeyConstraint(
            ["backtest_run_id"],
            ["backtest_runs.id"],
            name="fk_detected_setups_backtest_run_id_backtest_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_detected_setups_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["data_partition_id"],
            ["data_partitions.id"],
            name="fk_detected_setups_data_partition_id_data_partitions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_detected_setups"),
        sa.UniqueConstraint(
            "backtest_run_id", "setup_key", name="uq_detected_setups_backtest_setup_key"
        ),
    )
    op.create_index("ix_detected_setups_backtest_run_id", "detected_setups", ["backtest_run_id"])
    op.create_index("ix_detected_setups_instrument_id", "detected_setups", ["instrument_id"])
    op.create_index(
        "ix_detected_setups_data_partition_id", "detected_setups", ["data_partition_id"]
    )
    op.create_index("ix_detected_setups_setup_status", "detected_setups", ["setup_status"])
    op.create_index("ix_detected_setups_side", "detected_setups", ["side"])
    op.create_index("ix_detected_setups_timeframe", "detected_setups", ["timeframe"])
    op.create_index("ix_detected_setups_session_date", "detected_setups", ["session_date"])
    op.create_index("ix_detected_setups_detected_at", "detected_setups", ["detected_at"])
    op.create_index(
        "ix_detected_setups_instrument_timeframe_session_date",
        "detected_setups",
        ["instrument_id", "timeframe", "session_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_detected_setups_instrument_timeframe_session_date", table_name="detected_setups"
    )
    op.drop_index("ix_detected_setups_detected_at", table_name="detected_setups")
    op.drop_index("ix_detected_setups_session_date", table_name="detected_setups")
    op.drop_index("ix_detected_setups_timeframe", table_name="detected_setups")
    op.drop_index("ix_detected_setups_side", table_name="detected_setups")
    op.drop_index("ix_detected_setups_setup_status", table_name="detected_setups")
    op.drop_index("ix_detected_setups_data_partition_id", table_name="detected_setups")
    op.drop_index("ix_detected_setups_instrument_id", table_name="detected_setups")
    op.drop_index("ix_detected_setups_backtest_run_id", table_name="detected_setups")
    op.drop_table("detected_setups")
