"""Create simulated trades table.

Revision ID: 0006_simulated_trades_table
Revises: 0005_detected_setups_table
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_simulated_trades_table"
down_revision: str | None = "0005_detected_setups_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
            "exit_reason IS NULL OR exit_reason IN ('stop_hit', 'target_hit', "
            "'same_candle_stop', 'session_force_close', 'session_close', "
            "'invalidation', 'end_of_data', 'manual_rule_exit', 'cancelled')",
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
