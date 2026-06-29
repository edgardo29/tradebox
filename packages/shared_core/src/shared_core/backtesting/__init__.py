"""Shared backtesting logic."""

from shared_core.backtesting.candles import (
    REQUIRED_CANDLE_COLUMNS,
    BacktestCandle,
    BacktestCandleValidationError,
    backtest_candles_from_mappings,
    validate_backtest_candles,
)
from shared_core.backtesting.config import (
    DEFAULT_INITIAL_CAPITAL,
    MAX_LOCAL_BACKTEST_WINDOW,
    BacktestConfig,
    BacktestConfigError,
)
from shared_core.backtesting.loader import load_clean_ohlcv_parquet_bytes
from shared_core.backtesting.runner import BacktestRunner, BacktestRunResult
from shared_core.backtesting.strategy import BacktestStrategyResult, NoOpStrategy

__all__ = [
    "DEFAULT_INITIAL_CAPITAL",
    "MAX_LOCAL_BACKTEST_WINDOW",
    "REQUIRED_CANDLE_COLUMNS",
    "BacktestCandle",
    "BacktestCandleValidationError",
    "BacktestConfig",
    "BacktestConfigError",
    "BacktestRunner",
    "BacktestRunResult",
    "BacktestStrategyResult",
    "NoOpStrategy",
    "backtest_candles_from_mappings",
    "load_clean_ohlcv_parquet_bytes",
    "validate_backtest_candles",
]
