"""Backtest run ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BacktestRun(Base):
    """Metadata and results for a backtest execution."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        CheckConstraint(
            "run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_backtest_runs_run_status_allowed",
        ),
        CheckConstraint(
            "timeframe IN ('1m', '5m')",
            name="ck_backtest_runs_timeframe_allowed",
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_backtest_runs_end_date_after_start_date",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_backtest_runs_finished_at_after_started_at",
        ),
        Index("ix_backtest_runs_pipeline_run_id", "pipeline_run_id"),
        Index("ix_backtest_runs_instrument_id", "instrument_id"),
        Index("ix_backtest_runs_run_status", "run_status"),
        Index("ix_backtest_runs_strategy_name_version", "strategy_name", "strategy_version"),
        Index("ix_backtest_runs_strategy_config_hash", "strategy_config_hash"),
        Index(
            "ix_backtest_runs_instrument_timeframe_start_end",
            "instrument_id",
            "timeframe",
            "start_date",
            "end_date",
        ),
        Index("ix_backtest_runs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", name="fk_backtest_runs_pipeline_run_id_pipeline_runs"),
        nullable=True,
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", name="fk_backtest_runs_instrument_id_instruments"),
        nullable=False,
    )
    run_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    execution_assumptions_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    input_data_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    pipeline_run = relationship("PipelineRun", back_populates="backtest_runs")
    instrument = relationship("Instrument", back_populates="backtest_runs")
    detected_setups = relationship(
        "DetectedSetup", back_populates="backtest_run", cascade="all, delete-orphan"
    )
    simulated_trades = relationship(
        "SimulatedTrade", back_populates="backtest_run", cascade="all, delete-orphan"
    )
