"""Data partition ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DataPartition(Base):
    """Metadata for raw and clean market-data partitions."""

    __tablename__ = "data_partitions"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "vendor",
            "dataset",
            "timeframe",
            "session_date",
            name="uq_data_partitions_inst_vendor_dataset_timeframe_date",
        ),
        CheckConstraint(
            "vendor IN ('databento', 'manual', 'test')",
            name="ck_data_partitions_vendor_allowed",
        ),
        CheckConstraint(
            "timeframe IN ('1m', '5m')",
            name="ck_data_partitions_timeframe_allowed",
        ),
        CheckConstraint(
            "partition_status IN "
            "('pending', 'raw_available', 'clean_available', 'validated', 'failed')",
            name="ck_data_partitions_partition_status_allowed",
        ),
        CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_data_partitions_row_count_non_negative",
        ),
        CheckConstraint(
            "validation_error_count IS NULL OR validation_error_count >= 0",
            name="ck_data_partitions_validation_error_count_non_negative",
        ),
        Index("ix_data_partitions_instrument_id", "instrument_id"),
        Index("ix_data_partitions_pipeline_run_id", "pipeline_run_id"),
        Index("ix_data_partitions_session_date", "session_date"),
        Index("ix_data_partitions_partition_status", "partition_status"),
        Index("ix_data_partitions_timeframe", "timeframe"),
        Index("ix_data_partitions_vendor_dataset_timeframe", "vendor", "dataset", "timeframe"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", name="fk_data_partitions_instrument_id_instruments"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", name="fk_data_partitions_pipeline_run_id_pipeline_runs"),
        nullable=True,
    )
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset: Mapped[str] = mapped_column(String(128), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_file_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    clean_file_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    partition_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    validation_error_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clean_content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    instrument = relationship("Instrument", back_populates="data_partitions")
    pipeline_run = relationship("PipelineRun", back_populates="data_partitions")
    detected_setups = relationship("DetectedSetup", back_populates="data_partition")
