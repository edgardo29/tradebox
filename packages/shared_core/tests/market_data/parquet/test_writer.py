from datetime import UTC, datetime

import pyarrow.parquet as pq

from shared_core.market_data.clean.schema import CleanOhlcvBar
from shared_core.market_data.parquet import clean_ohlcv_rows_to_parquet_bytes


def test_clean_ohlcv_rows_to_parquet_bytes_writes_expected_schema() -> None:
    parquet_bytes = clean_ohlcv_rows_to_parquet_bytes(
        [
            CleanOhlcvBar(
                symbol="SPY",
                ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                session_date=datetime(2024, 1, 2, 14, 30, tzinfo=UTC).date(),
                timeframe="1m",
                open=472.18,
                high=472.65,
                low=472.06,
                close=472.52,
                volume=47_609,
                source_vendor="databento",
                source_dataset="EQUS.MINI",
                source_schema="ohlcv-1m",
                processed_at=datetime(2026, 6, 28, 12, tzinfo=UTC),
            )
        ]
    )

    table = pq.read_table(source=pa_buffer_reader(parquet_bytes))

    assert table.num_rows == 1
    assert table.column_names == [
        "symbol",
        "ts_event",
        "session_date",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source_vendor",
        "source_dataset",
        "source_schema",
        "processed_at",
    ]
    assert table.to_pylist()[0]["symbol"] == "SPY"
    assert table.to_pylist()[0]["source_dataset"] == "EQUS.MINI"


def pa_buffer_reader(content: bytes):
    import pyarrow as pa

    return pa.BufferReader(content)
