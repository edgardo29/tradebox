"""Inspect the existing raw SPY Databento smoke sample from private R2."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataPartition, Instrument
from app.db.session import SessionLocal
from shared_core.storage import R2ConfigError, load_r2_config_from_env, sha256_bytes
from shared_core.storage.r2_client import R2StorageClient


def _load_local_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def main() -> int:
    _load_local_env_file()

    try:
        r2_config = load_r2_config_from_env()
    except R2ConfigError as exc:
        print(f"R2 configuration error: {exc}", file=sys.stderr)
        return 2

    session = SessionLocal()
    try:
        partition, instrument = _load_latest_spy_partition(session)
        if partition.raw_object_path is None:
            raise RuntimeError("Latest SPY Databento partition has no raw_object_path.")

        raw_bytes = R2StorageClient(r2_config).read_bytes(partition.raw_object_path)
        content_hash = sha256_bytes(raw_bytes)
        hash_matches = content_hash == partition.raw_content_hash
        inspection = _inspect_dbn(raw_bytes)

        _print_report(
            partition=partition,
            instrument=instrument,
            bucket_name=r2_config.bucket_name,
            raw_size_bytes=len(raw_bytes),
            actual_content_hash=content_hash,
            hash_matches=hash_matches,
            inspection=inspection,
        )
        return 0
    except Exception as exc:
        print(f"Databento SPY sample inspection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


def _load_latest_spy_partition(session: Session) -> tuple[DataPartition, Instrument]:
    statement = (
        select(DataPartition, Instrument)
        .join(Instrument, DataPartition.instrument_id == Instrument.id)
        .where(
            Instrument.symbol == "SPY",
            DataPartition.vendor == "databento",
            DataPartition.raw_object_path.is_not(None),
        )
        .order_by(DataPartition.updated_at.desc())
    )
    row = session.execute(statement).first()
    if row is None:
        raise RuntimeError("No SPY Databento data_partitions row with raw_object_path was found.")
    return row


def _inspect_dbn(raw_bytes: bytes) -> dict[str, Any]:
    try:
        import databento as db
    except ModuleNotFoundError as exc:
        raise RuntimeError("databento is required to inspect DBN samples.") from exc

    store = db.DBNStore.from_bytes(raw_bytes)
    schema = str(store.schema) if store.schema is not None else None
    records = store.to_ndarray(schema=schema)
    record_count = len(records)
    first_record = _record_to_dict(records[0]) if record_count else {}

    return {
        "dataset": store.dataset,
        "schema": schema,
        "symbols": store.symbols,
        "stype_in": str(store.stype_in),
        "stype_out": str(store.stype_out),
        "start": str(store.start),
        "end": str(store.end) if store.end is not None else None,
        "limit": store.limit,
        "record_count": record_count,
        "dtype_fields": _dtype_fields(records),
        "first_record": first_record,
        "timestamp_summary": _timestamp_summary(first_record),
        "price_summary": _price_summary(first_record),
    }


def _dtype_fields(records: object) -> list[dict[str, str]]:
    dtype = getattr(records, "dtype", None)
    names = getattr(dtype, "names", None)
    if not names:
        return []
    return [{"name": name, "dtype": str(dtype.fields[name][0])} for name in names]


def _record_to_dict(record: object) -> dict[str, Any]:
    dtype = getattr(record, "dtype", None)
    names = getattr(dtype, "names", None)
    if not names:
        return {}
    return {name: _to_python_scalar(record[name]) for name in names}


def _to_python_scalar(value: object) -> object:
    if hasattr(value, "item"):
        return value.item()
    return value


def _timestamp_summary(record: dict[str, Any]) -> dict[str, str]:
    summary: dict[str, str] = {}
    for key, value in record.items():
        if key.startswith("ts_") and isinstance(value, int):
            summary[key] = datetime.fromtimestamp(value / 1_000_000_000, tz=UTC).isoformat()
    return summary


def _price_summary(record: dict[str, Any]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for key in ["open", "high", "low", "close"]:
        value = record.get(key)
        if isinstance(value, int):
            summary[key] = value / 1_000_000_000
    return summary


def _print_report(
    *,
    partition: DataPartition,
    instrument: Instrument,
    bucket_name: str,
    raw_size_bytes: int,
    actual_content_hash: str,
    hash_matches: bool,
    inspection: dict[str, Any],
) -> None:
    print("Databento SPY raw sample inspection")
    print("===================================")
    print("")
    print("data_partitions metadata")
    print(f"id={partition.id}")
    print(f"instrument_id={instrument.id}")
    print(f"instrument_symbol={instrument.symbol}")
    print(f"instrument_asset_class={instrument.asset_class}")
    print(f"vendor={partition.vendor}")
    print(f"dataset={partition.dataset}")
    print(f"timeframe={partition.timeframe}")
    print(f"session_date={partition.session_date}")
    print(f"partition_status={partition.partition_status}")
    print(f"raw_object_bucket={bucket_name}")
    print(f"raw_object_path={partition.raw_object_path}")
    print(f"raw_file_format={partition.raw_file_format}")
    print(f"raw_content_hash_stored={partition.raw_content_hash}")
    print(f"raw_content_hash_actual={actual_content_hash}")
    print(f"raw_content_hash_matches={hash_matches}")
    print(f"row_count_stored={partition.row_count}")
    print(f"raw_size_bytes={raw_size_bytes}")
    print("")
    print("raw DBN metadata")
    print(f"databento_dataset={inspection['dataset']}")
    print(f"databento_schema={inspection['schema']}")
    print(f"databento_symbols={inspection['symbols']}")
    print(f"databento_stype_in={inspection['stype_in']}")
    print(f"databento_stype_out={inspection['stype_out']}")
    print(f"databento_start={inspection['start']}")
    print(f"databento_end={inspection['end']}")
    print(f"databento_limit={inspection['limit']}")
    print(f"decoded_record_count={inspection['record_count']}")
    print("")
    print("raw fields")
    for field in inspection["dtype_fields"]:
        print(f"- {field['name']}: {field['dtype']}")
    print("")
    print("first raw record")
    for key, value in inspection["first_record"].items():
        print(f"{key}={value}")
    print("")
    print("timestamp interpretation")
    for key, value in inspection["timestamp_summary"].items():
        print(f"{key}_utc={value}")
    print("")
    print("price interpretation")
    for key, value in inspection["price_summary"].items():
        print(f"{key}_decimal={value}")
    print("")
    print("clean Parquet contract recommendation")
    print("columns=symbol, ts_event, session_date, timeframe, open, high, low, close, volume,")
    print("        source_vendor, source_dataset, source_schema, ingestion_run_id, processed_at")
    print("clean_path=clean/vendor=databento/dataset=<dataset>/symbol=SPY/timeframe=1m/")
    print("           session_date=<YYYY-MM-DD>/part-000.parquet")


if __name__ == "__main__":
    raise SystemExit(main())
