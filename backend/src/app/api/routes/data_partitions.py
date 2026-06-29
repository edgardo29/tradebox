"""Data partition API routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.data_partition import DataPartitionResponse
from app.services.data_partitions import get_data_partition, list_data_partitions

router = APIRouter(prefix="/data-partitions", tags=["data-partitions"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=list[DataPartitionResponse])
def list_data_partition_metadata(
    session: DbSession,
    instrument_id: uuid.UUID | None = None,
    symbol: str | None = Query(default=None, min_length=1),
    vendor: str | None = Query(default=None, min_length=1),
    dataset: str | None = Query(default=None, min_length=1),
    timeframe: str | None = Query(default=None, min_length=1),
    session_date: date | None = None,
    partition_status: str | None = Query(default=None, min_length=1),
) -> list[DataPartitionResponse]:
    """List data partition metadata."""
    return list_data_partitions(
        session,
        instrument_id=instrument_id,
        symbol=symbol,
        vendor=vendor,
        dataset=dataset,
        timeframe=timeframe,
        session_date=session_date,
        partition_status=partition_status,
    )


@router.get("/{partition_id}", response_model=DataPartitionResponse)
def get_data_partition_metadata(
    partition_id: uuid.UUID,
    session: DbSession,
) -> DataPartitionResponse:
    """Get one data partition metadata record."""
    partition = get_data_partition(session, partition_id)
    if partition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data partition not found.",
        )
    return partition
