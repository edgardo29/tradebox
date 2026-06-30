"""Simulated trade ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulatedTrade(Base):
    """A simulated trade produced by a backtest run."""

    __tablename__ = "simulated_trades"
    __table_args__ = (
        UniqueConstraint(
            "backtest_run_id", "trade_key", name="uq_simulated_trades_backtest_trade_key"
        ),
        CheckConstraint(
            "trade_status IN ('open', 'closed', 'cancelled')",
            name="ck_simulated_trades_trade_status_allowed",
        ),
        CheckConstraint("side IN ('long', 'short')", name="ck_simulated_trades_side_allowed"),
        CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN "
            "('stop_hit', 'target_hit', 'same_candle_stop', 'session_force_close', "
            "'session_close', 'invalidation', 'end_of_data', 'manual_rule_exit', 'cancelled')",
            name="ck_simulated_trades_exit_reason_allowed",
        ),
        CheckConstraint("entry_price > 0", name="ck_simulated_trades_entry_price_positive"),
        CheckConstraint(
            "exit_price IS NULL OR exit_price > 0",
            name="ck_simulated_trades_exit_price_positive",
        ),
        CheckConstraint(
            "stop_price IS NULL OR stop_price > 0",
            name="ck_simulated_trades_stop_price_positive",
        ),
        CheckConstraint(
            "target_price IS NULL OR target_price > 0",
            name="ck_simulated_trades_target_price_positive",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_simulated_trades_quantity_non_negative",
        ),
        CheckConstraint(
            "risk_amount IS NULL OR risk_amount >= 0",
            name="ck_simulated_trades_risk_amount_non_negative",
        ),
        CheckConstraint(
            "fees IS NULL OR fees >= 0",
            name="ck_simulated_trades_fees_non_negative",
        ),
        CheckConstraint(
            "slippage_amount IS NULL OR slippage_amount >= 0",
            name="ck_simulated_trades_slippage_amount_non_negative",
        ),
        CheckConstraint(
            "exit_at IS NULL OR exit_at >= entry_at",
            name="ck_simulated_trades_exit_at_after_entry_at",
        ),
        Index("ix_simulated_trades_backtest_run_id", "backtest_run_id"),
        Index("ix_simulated_trades_detected_setup_id", "detected_setup_id"),
        Index("ix_simulated_trades_instrument_id", "instrument_id"),
        Index("ix_simulated_trades_trade_status", "trade_status"),
        Index("ix_simulated_trades_side", "side"),
        Index("ix_simulated_trades_exit_reason", "exit_reason"),
        Index("ix_simulated_trades_entry_at", "entry_at"),
        Index("ix_simulated_trades_exit_at", "exit_at"),
        Index("ix_simulated_trades_instrument_trade_status", "instrument_id", "trade_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "backtest_runs.id",
            name="fk_simulated_trades_backtest_run_id_backtest_runs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    detected_setup_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "detected_setups.id",
            name="fk_simulated_trades_detected_setup_id_detected_setups",
        ),
        nullable=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", name="fk_simulated_trades_instrument_id_instruments"),
        nullable=False,
    )
    trade_key: Mapped[str] = mapped_column(String(128), nullable=False)
    trade_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'open'")
    )
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fees: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    slippage_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    r_multiple: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trade_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    backtest_run = relationship("BacktestRun", back_populates="simulated_trades")
    detected_setup = relationship("DetectedSetup", back_populates="simulated_trades")
    instrument = relationship("Instrument", back_populates="simulated_trades")
