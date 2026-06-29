"""Parquet writers for clean market-data rows."""

from __future__ import annotations

from shared_core.market_data.clean.schema import CleanOhlcvBar


def clean_ohlcv_rows_to_parquet_bytes(rows: list[CleanOhlcvBar]) -> bytes:
    """Write clean OHLCV rows to Parquet bytes."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required to write clean OHLCV Parquet.") from exc

    data = {
        "symbol": [row.symbol for row in rows],
        "ts_event": [row.ts_event for row in rows],
        "session_date": [row.session_date for row in rows],
        "timeframe": [row.timeframe for row in rows],
        "open": [row.open for row in rows],
        "high": [row.high for row in rows],
        "low": [row.low for row in rows],
        "close": [row.close for row in rows],
        "volume": [row.volume for row in rows],
        "source_vendor": [row.source_vendor for row in rows],
        "source_dataset": [row.source_dataset for row in rows],
        "source_schema": [row.source_schema for row in rows],
        "processed_at": [row.processed_at for row in rows],
    }
    schema = pa.schema(
        [
            ("symbol", pa.string()),
            ("ts_event", pa.timestamp("us", tz="UTC")),
            ("session_date", pa.date32()),
            ("timeframe", pa.string()),
            ("open", pa.float64()),
            ("high", pa.float64()),
            ("low", pa.float64()),
            ("close", pa.float64()),
            ("volume", pa.int64()),
            ("source_vendor", pa.string()),
            ("source_dataset", pa.string()),
            ("source_schema", pa.string()),
            ("processed_at", pa.timestamp("us", tz="UTC")),
        ]
    )
    table = pa.Table.from_pydict(data, schema=schema)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    return sink.getvalue().to_pybytes()
