"""Instrument ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Instrument(Base):
    """Tradable or referenceable market instrument."""

    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_instruments_symbol"),
        CheckConstraint(
            "asset_class IN " "('equity', 'etf', 'future', 'crypto', 'forex', 'index', 'other')",
            name="ck_instruments_asset_class_allowed",
        ),
        Index("ix_instruments_asset_class", "asset_class"),
        Index("ix_instruments_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'USD'"))
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'America/New_York'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    data_partitions = relationship("DataPartition", back_populates="instrument")
    backtest_runs = relationship("BacktestRun", back_populates="instrument")
    detected_setups = relationship("DetectedSetup", back_populates="instrument")
    simulated_trades = relationship("SimulatedTrade", back_populates="instrument")
