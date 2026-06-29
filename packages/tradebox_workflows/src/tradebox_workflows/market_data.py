"""Market-data workflow functions shared by scripts and Dagster assets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from uuid import uuid4

from app.db.models import DataPartition, Instrument
from app.db.session import SessionLocal
from app.schemas.data_partition import DataPartitionCreate
from app.services.data_partitions import get_data_partition, upsert_data_partition
from shared_core.market_data.clean import convert_databento_ohlcv_1m_dbn
from shared_core.market_data.databento import (
    DatabentoHistoricalClient,
    DatabentoSmokeRequest,
    databento_smoke_raw_object_key,
    load_databento_config_from_env,
)
from shared_core.market_data.parquet import clean_ohlcv_rows_to_parquet_bytes
from shared_core.storage import clean_ohlcv_object_key, load_r2_config_from_env, sha256_bytes
from shared_core.storage.r2_client import R2StorageClient
from sqlalchemy import select
from sqlalchemy.orm import Session

SessionFactory = Callable[[], Session]

SMOKE_VENDOR = "databento"
SMOKE_SCHEMA_VERSION = "1"


def describe_existing_raw_market_data_partition(
    *,
    symbol: str = "SPY",
    vendor: str = SMOKE_VENDOR,
    timeframe: str = "1m",
    dataset: str | None = None,
    session_date: date | None = None,
    session_factory: SessionFactory = SessionLocal,
) -> dict[str, object]:
    """Describe the latest matching raw partition without reading object storage."""

    session = session_factory()
    try:
        partition, instrument = load_latest_raw_partition(
            session,
            symbol=symbol,
            vendor=vendor,
            timeframe=timeframe,
            dataset=dataset,
            session_date=session_date,
        )
        return _raw_partition_metadata(partition, instrument)
    finally:
        session.close()


def ingest_databento_smoke_partition(
    request: DatabentoSmokeRequest,
    *,
    confirm_credit_use: bool,
    session_factory: SessionFactory = SessionLocal,
    r2_client: R2StorageClient | None = None,
    databento_client: DatabentoHistoricalClient | None = None,
) -> dict[str, object]:
    """Fetch a tiny Databento sample, store it in R2, and catalog it in Postgres."""

    if not confirm_credit_use:
        raise RuntimeError(
            "Live Databento smoke ingestion requires explicit credit-use confirmation."
        )

    r2_client = r2_client or R2StorageClient(load_r2_config_from_env())
    databento_client = databento_client or DatabentoHistoricalClient(
        load_databento_config_from_env()
    )
    run_id = uuid4()
    object_key = databento_smoke_raw_object_key(request, run_id)

    session = session_factory()
    try:
        raw_sample = databento_client.get_raw_sample(request)
        if raw_sample.record_count == 0:
            raise RuntimeError("Databento returned zero records for the smoke request.")

        r2_client.upload_bytes(
            object_key,
            raw_sample.content,
            content_type="application/zstd",
        )
        if not r2_client.object_exists(object_key):
            raise RuntimeError("Uploaded Databento raw object was not visible in R2.")

        instrument = get_or_create_instrument(session, request.symbol)
        partition = upsert_data_partition(
            session,
            DataPartitionCreate(
                instrument_id=instrument.id,
                vendor=SMOKE_VENDOR,
                dataset=request.dataset,
                timeframe=request.timeframe,
                session_date=date.fromisoformat(request.session_date),
                raw_object_path=object_key,
                raw_file_format=raw_sample.raw_file_format,
                partition_status="raw_available",
                row_count=raw_sample.record_count,
                validation_error_count=0,
                schema_version=SMOKE_SCHEMA_VERSION,
                raw_content_hash=raw_sample.content_hash,
            ),
            commit=True,
        )

        loaded_partition = get_data_partition(session, partition.id)
        if loaded_partition is None:
            raise RuntimeError("Created data_partitions row could not be read back.")
        if loaded_partition.raw_object_path != object_key:
            raise RuntimeError("Readback partition row has the wrong raw_object_path.")
        if loaded_partition.raw_content_hash != raw_sample.content_hash:
            raise RuntimeError("Readback partition row has the wrong raw_content_hash.")

        return {
            "dataset": request.dataset,
            "schema": request.schema,
            "symbol": request.symbol,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "limit": request.limit,
            "record_count": raw_sample.record_count,
            "bucket": r2_client.config.bucket_name,
            "raw_object_path": object_key,
            "instrument_id": instrument.id,
            "data_partition_id": loaded_partition.id,
            "raw_content_hash": raw_sample.content_hash,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def raw_databento_partition_to_clean(
    *,
    symbol: str = "SPY",
    session_factory: SessionFactory = SessionLocal,
    r2_client: R2StorageClient | None = None,
) -> dict[str, object]:
    """Convert the latest raw Databento partition into clean Parquet in R2."""

    r2_client = r2_client or R2StorageClient(load_r2_config_from_env())
    session = session_factory()
    try:
        partition, instrument = load_latest_raw_partition(
            session,
            symbol=symbol,
            vendor=SMOKE_VENDOR,
            timeframe="1m",
            dataset=None,
            session_date=None,
        )
        if partition.raw_object_path is None:
            raise RuntimeError("Latest Databento partition has no raw_object_path.")

        raw_bytes = r2_client.read_bytes(partition.raw_object_path)
        raw_hash = sha256_bytes(raw_bytes)
        if partition.raw_content_hash and raw_hash != partition.raw_content_hash:
            raise RuntimeError("Raw content hash does not match data_partitions metadata.")

        conversion = convert_databento_ohlcv_1m_dbn(raw_bytes, symbol=instrument.symbol)
        parquet_bytes = clean_ohlcv_rows_to_parquet_bytes(conversion.rows)
        clean_hash = sha256_bytes(parquet_bytes)
        clean_key = clean_ohlcv_object_key(
            vendor=SMOKE_VENDOR,
            dataset=conversion.source_dataset,
            symbol=instrument.symbol,
            timeframe=conversion.timeframe,
            session_date=conversion.session_date,
        )

        r2_client.upload_bytes(
            clean_key,
            parquet_bytes,
            content_type="application/vnd.apache.parquet",
        )
        if not r2_client.object_exists(clean_key):
            raise RuntimeError("Clean Parquet object was not visible in R2 after upload.")

        partition.clean_object_path = clean_key
        partition.clean_file_format = "parquet"
        partition.clean_content_hash = clean_hash
        partition.dataset = conversion.source_dataset
        partition.row_count = len(conversion.rows)
        partition.validation_error_count = 0
        partition.partition_status = "validated"
        partition.error_message = None
        session.commit()
        session.refresh(partition)

        loaded_partition = get_data_partition(session, partition.id)
        if loaded_partition is None:
            raise RuntimeError("Updated data_partitions row could not be read back.")
        if loaded_partition.clean_object_path != clean_key:
            raise RuntimeError("Readback partition row has the wrong clean_object_path.")
        if loaded_partition.clean_content_hash != clean_hash:
            raise RuntimeError("Readback partition row has the wrong clean_content_hash.")

        return {
            "partition_id": loaded_partition.id,
            "instrument_symbol": instrument.symbol,
            "raw_object_path": loaded_partition.raw_object_path,
            "clean_object_path": loaded_partition.clean_object_path,
            "clean_file_format": loaded_partition.clean_file_format,
            "row_count": loaded_partition.row_count,
            "validation_error_count": loaded_partition.validation_error_count,
            "partition_status": loaded_partition.partition_status,
            "clean_content_hash": loaded_partition.clean_content_hash,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_latest_raw_partition(
    session: Session,
    *,
    symbol: str,
    vendor: str,
    timeframe: str,
    dataset: str | None,
    session_date: date | None,
) -> tuple[DataPartition, Instrument]:
    """Load the latest matching raw partition and instrument."""

    statement = (
        select(DataPartition, Instrument)
        .join(Instrument, DataPartition.instrument_id == Instrument.id)
        .where(
            Instrument.symbol == symbol.strip().upper(),
            DataPartition.vendor == vendor,
            DataPartition.timeframe == timeframe,
            DataPartition.raw_object_path.is_not(None),
        )
        .order_by(DataPartition.updated_at.desc())
    )
    if dataset is not None:
        statement = statement.where(DataPartition.dataset == dataset)
    if session_date is not None:
        statement = statement.where(DataPartition.session_date == session_date)

    row = session.execute(statement).first()
    if row is None:
        raise RuntimeError("No matching market-data partition with raw_object_path was found.")
    return row


def get_or_create_instrument(session: Session, symbol: str) -> Instrument:
    """Load or create the instrument row used by smoke workflows."""

    normalized_symbol = symbol.strip().upper()
    instrument = session.scalars(
        select(Instrument).where(Instrument.symbol == normalized_symbol)
    ).one_or_none()
    if instrument is not None:
        return instrument

    instrument = Instrument(
        symbol=normalized_symbol,
        name=f"{normalized_symbol} smoke test instrument",
        asset_class="etf" if normalized_symbol == "SPY" else "equity",
        exchange="NYSEARCA" if normalized_symbol == "SPY" else None,
    )
    session.add(instrument)
    session.flush()
    return instrument


def _raw_partition_metadata(partition: DataPartition, instrument: Instrument) -> dict[str, object]:
    return {
        "partition_id": partition.id,
        "instrument_id": instrument.id,
        "instrument_symbol": instrument.symbol,
        "vendor": partition.vendor,
        "dataset": partition.dataset,
        "timeframe": partition.timeframe,
        "session_date": partition.session_date,
        "raw_object_path": partition.raw_object_path,
        "raw_file_format": partition.raw_file_format,
        "raw_content_hash": partition.raw_content_hash,
        "clean_object_path": partition.clean_object_path,
        "clean_file_format": partition.clean_file_format,
        "clean_content_hash": partition.clean_content_hash,
        "row_count": partition.row_count,
        "validation_error_count": partition.validation_error_count,
        "partition_status": partition.partition_status,
        "schema_version": partition.schema_version,
    }
