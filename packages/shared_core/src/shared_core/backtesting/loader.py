"""Load clean market-data inputs for backtesting."""

from __future__ import annotations

from shared_core.backtesting.candles import BacktestCandle, backtest_candles_from_mappings


def load_clean_ohlcv_parquet_bytes(content: bytes) -> list[BacktestCandle]:
    """Load clean OHLCV candles from Parquet bytes."""

    if not content:
        raise ValueError("Clean OHLCV Parquet content must not be empty.")

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required to load clean OHLCV Parquet.") from exc

    table = pq.read_table(pa.BufferReader(content))
    return backtest_candles_from_mappings(table.to_pylist())
