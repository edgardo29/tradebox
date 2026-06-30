"""Create backtest runs table.

Revision ID: 0004_backtest_runs_table
Revises: 0003_data_partitions_table
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_backtest_runs_table"
down_revision: str | None = "0003_data_partitions_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "run_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("strategy_config_hash", sa.String(length=128), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "execution_assumptions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "input_data_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metrics_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            "run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_backtest_runs_run_status_allowed",
        ),
        sa.CheckConstraint("timeframe IN ('1m', '5m')", name="ck_backtest_runs_timeframe_allowed"),
        sa.CheckConstraint(
            "end_date >= start_date", name="ck_backtest_runs_end_date_after_start_date"
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_backtest_runs_finished_at_after_started_at",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name="fk_backtest_runs_pipeline_run_id_pipeline_runs",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], name="fk_backtest_runs_instrument_id_instruments"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_runs"),
    )
    op.create_index("ix_backtest_runs_pipeline_run_id", "backtest_runs", ["pipeline_run_id"])
    op.create_index("ix_backtest_runs_instrument_id", "backtest_runs", ["instrument_id"])
    op.create_index("ix_backtest_runs_run_status", "backtest_runs", ["run_status"])
    op.create_index(
        "ix_backtest_runs_strategy_name_version",
        "backtest_runs",
        ["strategy_name", "strategy_version"],
    )
    op.create_index(
        "ix_backtest_runs_strategy_config_hash", "backtest_runs", ["strategy_config_hash"]
    )
    op.create_index(
        "ix_backtest_runs_instrument_timeframe_start_end",
        "backtest_runs",
        ["instrument_id", "timeframe", "start_date", "end_date"],
    )
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_instrument_timeframe_start_end", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_config_hash", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_name_version", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_run_status", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_instrument_id", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_pipeline_run_id", table_name="backtest_runs")
    op.drop_table("backtest_runs")
