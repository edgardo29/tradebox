"""Pipeline run ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PipelineRun(Base):
    """Metadata for an orchestration or manual pipeline run."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        UniqueConstraint("dagster_run_id", name="uq_pipeline_runs_dagster_run_id"),
        CheckConstraint(
            "run_type IN "
            "('market_data_ingestion', 'raw_to_clean_conversion', "
            "'setup_detection', 'backtest', 'manual')",
            name="ck_pipeline_runs_run_type_allowed",
        ),
        CheckConstraint(
            "run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_run_status_allowed",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_runs_finished_at_after_started_at",
        ),
        Index("ix_pipeline_runs_run_type", "run_type"),
        Index("ix_pipeline_runs_run_status", "run_status"),
        Index("ix_pipeline_runs_started_at", "started_at"),
        Index("ix_pipeline_runs_run_type_run_status", "run_type", "run_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    dagster_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    data_partitions = relationship("DataPartition", back_populates="pipeline_run")
    backtest_runs = relationship("BacktestRun", back_populates="pipeline_run")
