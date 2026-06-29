"""Data partition API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DataPartitionResponse(BaseModel):
    """API response shape for data partition metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    instrument_symbol: str | None = None
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


class DataPartitionCreate(BaseModel):
    """Internal/dev-safe data partition creation shape."""

    instrument_id: uuid.UUID
    pipeline_run_id: uuid.UUID | None = None
    vendor: str
    dataset: str
    timeframe: str
    session_date: date
    raw_object_path: str | None = None
    clean_object_path: str | None = None
    raw_file_format: str | None = None
    clean_file_format: str | None = None
    partition_status: str = "pending"
    row_count: int | None = None
    validation_error_count: int | None = None
    schema_version: str | None = None
    raw_content_hash: str | None = None
    clean_content_hash: str | None = None
    error_message: str | None = None
