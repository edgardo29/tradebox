"""Create core trading tables.

Revision ID: 0001_create_core_trading_tables
Revises:
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_create_core_trading_tables"
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

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column(
            "run_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("dagster_run_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            "run_type IN ('market_data_ingestion', 'raw_to_clean_conversion', "
            "'setup_detection', 'backtest', 'manual')",
            name="ck_pipeline_runs_run_type_allowed",
        ),
        sa.CheckConstraint(
            "run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_run_status_allowed",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_runs_finished_at_after_started_at",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_runs"),
        sa.UniqueConstraint("dagster_run_id", name="uq_pipeline_runs_dagster_run_id"),
    )
    op.create_index("ix_pipeline_runs_run_type", "pipeline_runs", ["run_type"])
    op.create_index("ix_pipeline_runs_run_status", "pipeline_runs", ["run_status"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.create_index(
        "ix_pipeline_runs_run_type_run_status", "pipeline_runs", ["run_type", "run_status"]
    )

    op.create_table(
        "data_partitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=128), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("raw_object_path", sa.Text(), nullable=True),
        sa.Column("clean_object_path", sa.Text(), nullable=True),
        sa.Column("raw_file_format", sa.String(length=32), nullable=True),
        sa.Column("clean_file_format", sa.String(length=32), nullable=True),
        sa.Column(
            "partition_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("validation_error_count", sa.BigInteger(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("raw_content_hash", sa.String(length=128), nullable=True),
        sa.Column("clean_content_hash", sa.String(length=128), nullable=True),
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
            "vendor IN ('databento', 'manual', 'test')", name="ck_data_partitions_vendor_allowed"
        ),
        sa.CheckConstraint(
            "timeframe IN ('1m', '5m')", name="ck_data_partitions_timeframe_allowed"
        ),
        sa.CheckConstraint(
            "partition_status IN ('pending', 'raw_available', 'clean_available', "
            "'validated', 'failed')",
            name="ck_data_partitions_partition_status_allowed",
        ),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0", name="ck_data_partitions_row_count_non_negative"
        ),
        sa.CheckConstraint(
            "validation_error_count IS NULL OR validation_error_count >= 0",
            name="ck_data_partitions_validation_error_count_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_data_partitions_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name="fk_data_partitions_pipeline_run_id_pipeline_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_partitions"),
        sa.UniqueConstraint(
            "instrument_id",
            "vendor",
            "dataset",
            "timeframe",
            "session_date",
            name="uq_data_partitions_inst_vendor_dataset_timeframe_date",
        ),
    )
    op.create_index("ix_data_partitions_instrument_id", "data_partitions", ["instrument_id"])
    op.create_index("ix_data_partitions_pipeline_run_id", "data_partitions", ["pipeline_run_id"])
    op.create_index("ix_data_partitions_session_date", "data_partitions", ["session_date"])
    op.create_index("ix_data_partitions_partition_status", "data_partitions", ["partition_status"])
    op.create_index("ix_data_partitions_timeframe", "data_partitions", ["timeframe"])
    op.create_index(
        "ix_data_partitions_vendor_dataset_timeframe",
        "data_partitions",
        ["vendor", "dataset", "timeframe"],
    )

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
            server_default=sa.text("'detected'"),
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
            "setup_status IN ('detected', 'triggered', 'invalidated', 'rejected', 'skipped')",
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

    op.create_table(
        "simulated_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backtest_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_setup_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_key", sa.String(length=128), nullable=False),
        sa.Column(
            "trade_status", sa.String(length=32), server_default=sa.text("'open'"), nullable=False
        ),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("stop_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("risk_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(18, 4), nullable=True),
        sa.Column("net_pnl", sa.Numeric(18, 4), nullable=True),
        sa.Column("fees", sa.Numeric(18, 4), nullable=True),
        sa.Column("slippage_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("r_multiple", sa.Numeric(18, 6), nullable=True),
        sa.Column("exit_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "trade_metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            "trade_status IN ('open', 'closed', 'cancelled')",
            name="ck_simulated_trades_trade_status_allowed",
        ),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_simulated_trades_side_allowed"),
        sa.CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN ('target_hit', 'stop_hit', "
            "'session_close', 'invalidation', 'end_of_data', "
            "'manual_rule_exit', 'cancelled')",
            name="ck_simulated_trades_exit_reason_allowed",
        ),
        sa.CheckConstraint("entry_price > 0", name="ck_simulated_trades_entry_price_positive"),
        sa.CheckConstraint(
            "exit_price IS NULL OR exit_price > 0", name="ck_simulated_trades_exit_price_positive"
        ),
        sa.CheckConstraint(
            "stop_price IS NULL OR stop_price > 0", name="ck_simulated_trades_stop_price_positive"
        ),
        sa.CheckConstraint(
            "target_price IS NULL OR target_price > 0",
            name="ck_simulated_trades_target_price_positive",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name="ck_simulated_trades_quantity_non_negative"
        ),
        sa.CheckConstraint(
            "risk_amount IS NULL OR risk_amount >= 0",
            name="ck_simulated_trades_risk_amount_non_negative",
        ),
        sa.CheckConstraint(
            "fees IS NULL OR fees >= 0", name="ck_simulated_trades_fees_non_negative"
        ),
        sa.CheckConstraint(
            "slippage_amount IS NULL OR slippage_amount >= 0",
            name="ck_simulated_trades_slippage_amount_non_negative",
        ),
        sa.CheckConstraint(
            "exit_at IS NULL OR exit_at >= entry_at",
            name="ck_simulated_trades_exit_at_after_entry_at",
        ),
        sa.ForeignKeyConstraint(
            ["backtest_run_id"],
            ["backtest_runs.id"],
            name="fk_simulated_trades_backtest_run_id_backtest_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["detected_setup_id"],
            ["detected_setups.id"],
            name="fk_simulated_trades_detected_setup_id_detected_setups",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_simulated_trades_instrument_id_instruments",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_simulated_trades"),
        sa.UniqueConstraint(
            "backtest_run_id", "trade_key", name="uq_simulated_trades_backtest_trade_key"
        ),
    )
    op.create_index("ix_simulated_trades_backtest_run_id", "simulated_trades", ["backtest_run_id"])
    op.create_index(
        "ix_simulated_trades_detected_setup_id", "simulated_trades", ["detected_setup_id"]
    )
    op.create_index("ix_simulated_trades_instrument_id", "simulated_trades", ["instrument_id"])
    op.create_index("ix_simulated_trades_trade_status", "simulated_trades", ["trade_status"])
    op.create_index("ix_simulated_trades_side", "simulated_trades", ["side"])
    op.create_index("ix_simulated_trades_exit_reason", "simulated_trades", ["exit_reason"])
    op.create_index("ix_simulated_trades_entry_at", "simulated_trades", ["entry_at"])
    op.create_index("ix_simulated_trades_exit_at", "simulated_trades", ["exit_at"])
    op.create_index(
        "ix_simulated_trades_instrument_trade_status",
        "simulated_trades",
        ["instrument_id", "trade_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_simulated_trades_instrument_trade_status", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_exit_at", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_entry_at", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_exit_reason", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_side", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_trade_status", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_instrument_id", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_detected_setup_id", table_name="simulated_trades")
    op.drop_index("ix_simulated_trades_backtest_run_id", table_name="simulated_trades")
    op.drop_table("simulated_trades")

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

    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_instrument_timeframe_start_end", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_config_hash", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_name_version", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_run_status", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_instrument_id", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_pipeline_run_id", table_name="backtest_runs")
    op.drop_table("backtest_runs")

    op.drop_index("ix_data_partitions_vendor_dataset_timeframe", table_name="data_partitions")
    op.drop_index("ix_data_partitions_timeframe", table_name="data_partitions")
    op.drop_index("ix_data_partitions_partition_status", table_name="data_partitions")
    op.drop_index("ix_data_partitions_session_date", table_name="data_partitions")
    op.drop_index("ix_data_partitions_pipeline_run_id", table_name="data_partitions")
    op.drop_index("ix_data_partitions_instrument_id", table_name="data_partitions")
    op.drop_table("data_partitions")

    op.drop_index("ix_pipeline_runs_run_type_run_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_type", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_index("ix_instruments_is_active", table_name="instruments")
    op.drop_index("ix_instruments_asset_class", table_name="instruments")
    op.drop_table("instruments")
