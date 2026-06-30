"""Detected setup ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DetectedSetup(Base):
    """A strategy setup detected during a backtest run."""

    __tablename__ = "detected_setups"
    __table_args__ = (
        UniqueConstraint(
            "backtest_run_id", "setup_key", name="uq_detected_setups_backtest_setup_key"
        ),
        CheckConstraint(
            "setup_status IN ('pending_entry', 'triggered', 'expired', 'filtered_out', "
            "'invalidated', 'detected', 'rejected', 'skipped')",
            name="ck_detected_setups_setup_status_allowed",
        ),
        CheckConstraint("side IN ('long', 'short')", name="ck_detected_setups_side_allowed"),
        CheckConstraint(
            "timeframe IN ('1m', '5m')",
            name="ck_detected_setups_timeframe_allowed",
        ),
        CheckConstraint(
            "entry_price IS NULL OR entry_price > 0",
            name="ck_detected_setups_entry_price_positive",
        ),
        CheckConstraint(
            "stop_price IS NULL OR stop_price > 0",
            name="ck_detected_setups_stop_price_positive",
        ),
        CheckConstraint(
            "target_price IS NULL OR target_price > 0",
            name="ck_detected_setups_target_price_positive",
        ),
        CheckConstraint(
            "invalidation_price IS NULL OR invalidation_price > 0",
            name="ck_detected_setups_invalidation_price_positive",
        ),
        Index("ix_detected_setups_backtest_run_id", "backtest_run_id"),
        Index("ix_detected_setups_instrument_id", "instrument_id"),
        Index("ix_detected_setups_data_partition_id", "data_partition_id"),
        Index("ix_detected_setups_setup_status", "setup_status"),
        Index("ix_detected_setups_side", "side"),
        Index("ix_detected_setups_timeframe", "timeframe"),
        Index("ix_detected_setups_session_date", "session_date"),
        Index("ix_detected_setups_detected_at", "detected_at"),
        Index(
            "ix_detected_setups_instrument_timeframe_session_date",
            "instrument_id",
            "timeframe",
            "session_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "backtest_runs.id",
            name="fk_detected_setups_backtest_run_id_backtest_runs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", name="fk_detected_setups_instrument_id_instruments"),
        nullable=False,
    )
    data_partition_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "data_partitions.id",
            name="fk_detected_setups_data_partition_id_data_partitions",
        ),
        nullable=True,
    )
    setup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    setup_status: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    setup_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    setup_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invalidation_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    setup_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    backtest_run = relationship("BacktestRun", back_populates="detected_setups")
    instrument = relationship("Instrument", back_populates="detected_setups")
    data_partition = relationship("DataPartition", back_populates="detected_setups")
    simulated_trades = relationship("SimulatedTrade", back_populates="detected_setup")
