"""Data partition database workflows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import DataPartition, Instrument
from app.schemas.data_partition import DataPartitionCreate


@dataclass(frozen=True)
class DataPartitionMetadata:
    """API-facing data partition metadata with instrument symbol."""

    id: uuid.UUID
    instrument_id: uuid.UUID
    instrument_symbol: str | None
    pipeline_run_id: uuid.UUID | None
    vendor: str
    dataset: str
    timeframe: str
    session_date: date
    raw_object_path: str | None
    clean_object_path: str | None
    raw_file_format: str | None
    clean_file_format: str | None
    partition_status: str
    row_count: int | None
    validation_error_count: int | None
    schema_version: str | None
    raw_content_hash: str | None
    clean_content_hash: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


def list_data_partitions(
    session: Session,
    *,
    instrument_id: uuid.UUID | None = None,
    symbol: str | None = None,
    vendor: str | None = None,
    dataset: str | None = None,
    timeframe: str | None = None,
    session_date: date | None = None,
    partition_status: str | None = None,
) -> list[DataPartitionMetadata]:
    """List data partitions with optional metadata filters."""
    statement = select(DataPartition, Instrument.symbol).join(
        Instrument, DataPartition.instrument_id == Instrument.id
    )
    statement = _apply_filters(
        statement,
        instrument_id=instrument_id,
        symbol=symbol,
        vendor=vendor,
        dataset=dataset,
        timeframe=timeframe,
        session_date=session_date,
        partition_status=partition_status,
    )
    statement = statement.order_by(
        DataPartition.session_date.desc(),
        DataPartition.vendor,
        DataPartition.dataset,
        DataPartition.timeframe,
    )
    return [
        _to_metadata(partition, instrument_symbol)
        for partition, instrument_symbol in session.execute(statement).all()
    ]


def get_data_partition(session: Session, partition_id: uuid.UUID) -> DataPartitionMetadata | None:
    """Get one data partition by id."""
    statement = (
        select(DataPartition, Instrument.symbol)
        .join(Instrument, DataPartition.instrument_id == Instrument.id)
        .where(DataPartition.id == partition_id)
    )
    row = session.execute(statement).one_or_none()
    if row is None:
        return None
    partition, instrument_symbol = row
    return _to_metadata(partition, instrument_symbol)


def upsert_data_partition(
    session: Session, data: DataPartitionCreate, *, commit: bool = False
) -> DataPartition:
    """Create or update a data partition by its natural partition identity."""
    statement = select(DataPartition).where(
        DataPartition.instrument_id == data.instrument_id,
        DataPartition.vendor == data.vendor,
        DataPartition.dataset == data.dataset,
        DataPartition.timeframe == data.timeframe,
        DataPartition.session_date == data.session_date,
    )
    partition = session.scalars(statement).one_or_none()

    if partition is None:
        partition = DataPartition(**data.model_dump())
        session.add(partition)
    else:
        for field_name, value in data.model_dump().items():
            setattr(partition, field_name, value)

    session.flush()
    if commit:
        session.commit()
        session.refresh(partition)
    return partition


def _apply_filters(
    statement: Select[tuple[DataPartition, str]],
    *,
    instrument_id: uuid.UUID | None,
    symbol: str | None,
    vendor: str | None,
    dataset: str | None,
    timeframe: str | None,
    session_date: date | None,
    partition_status: str | None,
) -> Select[tuple[DataPartition, str]]:
    if instrument_id is not None:
        statement = statement.where(DataPartition.instrument_id == instrument_id)
    if symbol is not None:
        statement = statement.where(Instrument.symbol == symbol.upper())
    if vendor is not None:
        statement = statement.where(DataPartition.vendor == vendor)
    if dataset is not None:
        statement = statement.where(DataPartition.dataset == dataset)
    if timeframe is not None:
        statement = statement.where(DataPartition.timeframe == timeframe)
    if session_date is not None:
        statement = statement.where(DataPartition.session_date == session_date)
    if partition_status is not None:
        statement = statement.where(DataPartition.partition_status == partition_status)
    return statement


def _to_metadata(partition: DataPartition, instrument_symbol: str | None) -> DataPartitionMetadata:
    return DataPartitionMetadata(
        id=partition.id,
        instrument_id=partition.instrument_id,
        instrument_symbol=instrument_symbol,
        pipeline_run_id=partition.pipeline_run_id,
        vendor=partition.vendor,
        dataset=partition.dataset,
        timeframe=partition.timeframe,
        session_date=partition.session_date,
        raw_object_path=partition.raw_object_path,
        clean_object_path=partition.clean_object_path,
        raw_file_format=partition.raw_file_format,
        clean_file_format=partition.clean_file_format,
        partition_status=partition.partition_status,
        row_count=partition.row_count,
        validation_error_count=partition.validation_error_count,
        schema_version=partition.schema_version,
        raw_content_hash=partition.raw_content_hash,
        clean_content_hash=partition.clean_content_hash,
        error_message=partition.error_message,
        created_at=partition.created_at,
        updated_at=partition.updated_at,
    )
