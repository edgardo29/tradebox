"""Raw Databento OHLCV conversion helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from shared_core.market_data.clean.schema import CleanOhlcvBar
from shared_core.market_data.clean.validation import validate_clean_ohlcv

PRICE_SCALE = 1_000_000_000
SOURCE_VENDOR_DATABENTO = "databento"


@dataclass(frozen=True)
class CleanOhlcvConversionResult:
    """Clean conversion result and source metadata."""

    rows: list[CleanOhlcvBar]
    source_dataset: str
    source_schema: str
    timeframe: str
    session_date: str


def convert_databento_ohlcv_1m_dbn(
    raw_bytes: bytes,
    *,
    symbol: str,
    processed_at: datetime | None = None,
) -> CleanOhlcvConversionResult:
    """Convert Databento OHLCV-1m DBN bytes into clean OHLCV bars."""
    try:
        import databento as db
    except ModuleNotFoundError as exc:
        raise RuntimeError("databento is required to convert DBN samples.") from exc

    store = db.DBNStore.from_bytes(raw_bytes)
    source_schema = str(store.schema) if store.schema is not None else ""
    if source_schema != "ohlcv-1m":
        raise ValueError(f"Unsupported Databento schema for clean conversion: {source_schema}")

    records = store.to_ndarray(schema=source_schema)
    rows = convert_databento_ohlcv_records(
        records,
        symbol=symbol,
        source_dataset=store.dataset,
        source_schema=source_schema,
        timeframe="1m",
        processed_at=processed_at,
    )
    validate_clean_ohlcv(rows, expected_timeframe="1m")
    return CleanOhlcvConversionResult(
        rows=rows,
        source_dataset=store.dataset,
        source_schema=source_schema,
        timeframe="1m",
        session_date=rows[0].session_date.isoformat(),
    )


def convert_databento_ohlcv_records(
    records: Iterable[object],
    *,
    symbol: str,
    source_dataset: str,
    source_schema: str,
    timeframe: str,
    processed_at: datetime | None = None,
) -> list[CleanOhlcvBar]:
    """Convert Databento OHLCV-like records into clean OHLCV bars."""
    processed_at = processed_at or datetime.now(UTC)
    rows = [
        _record_to_clean_bar(
            _record_to_mapping(record),
            symbol=symbol,
            source_dataset=source_dataset,
            source_schema=source_schema,
            timeframe=timeframe,
            processed_at=processed_at,
        )
        for record in records
    ]
    validate_clean_ohlcv(rows, expected_timeframe=timeframe)
    return rows


def _record_to_clean_bar(
    record: Mapping[str, Any],
    *,
    symbol: str,
    source_dataset: str,
    source_schema: str,
    timeframe: str,
    processed_at: datetime,
) -> CleanOhlcvBar:
    ts_event = _timestamp_from_ns(_required_int(record, "ts_event"))
    return CleanOhlcvBar(
        symbol=symbol,
        ts_event=ts_event,
        session_date=ts_event.date(),
        timeframe=timeframe,
        open=_price_from_fixed(record, "open"),
        high=_price_from_fixed(record, "high"),
        low=_price_from_fixed(record, "low"),
        close=_price_from_fixed(record, "close"),
        volume=_required_int(record, "volume"),
        source_vendor=SOURCE_VENDOR_DATABENTO,
        source_dataset=source_dataset,
        source_schema=source_schema,
        processed_at=processed_at,
    )


def _record_to_mapping(record: object) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return record

    dtype = getattr(record, "dtype", None)
    names = getattr(dtype, "names", None)
    if not names:
        raise ValueError("Databento OHLCV record has no named fields.")
    return {name: _to_python_scalar(record[name]) for name in names}


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if value is None:
        raise ValueError(f"Databento OHLCV record is missing {field_name}.")
    return int(value)


def _price_from_fixed(record: Mapping[str, Any], field_name: str) -> float:
    return _required_int(record, field_name) / PRICE_SCALE


def _timestamp_from_ns(value: int) -> datetime:
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=nanos // 1_000)


def _to_python_scalar(value: object) -> object:
    if hasattr(value, "item"):
        return value.item()
    return value
