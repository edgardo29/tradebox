from datetime import UTC, date, datetime

import pytest

from shared_core.backtesting import load_clean_ohlcv_parquet_bytes
from shared_core.market_data.clean import CleanOhlcvBar
from shared_core.market_data.parquet import clean_ohlcv_rows_to_parquet_bytes


def test_load_clean_ohlcv_parquet_bytes_reads_clean_candles() -> None:
    content = clean_ohlcv_rows_to_parquet_bytes(
        [
            CleanOhlcvBar(
                symbol="SPY",
                ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                session_date=date(2024, 1, 2),
                timeframe="1m",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                source_vendor="databento",
                source_dataset="EQUS.MINI",
                source_schema="ohlcv-1m",
                processed_at=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
            )
        ]
    )

    candles = load_clean_ohlcv_parquet_bytes(content)

    assert len(candles) == 1
    assert candles[0].symbol == "SPY"
    assert candles[0].close == 100.5


def test_load_clean_ohlcv_parquet_bytes_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        load_clean_ohlcv_parquet_bytes(b"")
