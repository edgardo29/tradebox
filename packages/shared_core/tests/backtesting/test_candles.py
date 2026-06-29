from datetime import UTC, date, datetime, timedelta

import pytest

from shared_core.backtesting import (
    BacktestCandle,
    BacktestCandleValidationError,
    backtest_candles_from_mappings,
    validate_backtest_candles,
)


def test_backtest_candles_from_mappings_validates_required_columns() -> None:
    candles = backtest_candles_from_mappings([_row()])

    assert candles == [_candle()]


def test_backtest_candle_validation_rejects_empty_data() -> None:
    with pytest.raises(BacktestCandleValidationError, match="must not be empty"):
        validate_backtest_candles([])


def test_backtest_candle_validation_rejects_missing_columns() -> None:
    row = _row()
    row.pop("close")

    with pytest.raises(BacktestCandleValidationError, match="missing required columns"):
        backtest_candles_from_mappings([row])


def test_backtest_candle_validation_rejects_unsorted_timestamps() -> None:
    later = _candle(ts_event=datetime(2024, 1, 2, 14, 31, tzinfo=UTC))
    earlier = _candle(ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC))

    with pytest.raises(BacktestCandleValidationError, match="sorted"):
        validate_backtest_candles([later, earlier])


def test_backtest_candle_validation_rejects_duplicate_timestamps() -> None:
    candle = _candle()

    with pytest.raises(BacktestCandleValidationError, match="duplicate"):
        validate_backtest_candles([candle, candle])


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("open", 0, "positive"),
        ("volume", -1, "non-negative"),
    ],
)
def test_backtest_candle_validation_rejects_invalid_values(
    field_name: str,
    value: float,
    message: str,
) -> None:
    row = _row()
    row[field_name] = value

    with pytest.raises(BacktestCandleValidationError, match=message):
        backtest_candles_from_mappings([row])


def test_backtest_candle_validation_rejects_invalid_ohlc_relationships() -> None:
    row = _row()
    row["high"] = 99.5

    with pytest.raises(BacktestCandleValidationError, match=">= open and close"):
        backtest_candles_from_mappings([row])


def test_backtest_candle_validation_checks_config_symbol_and_timeframe() -> None:
    candle = _candle()

    with pytest.raises(BacktestCandleValidationError, match="symbol"):
        validate_backtest_candles([candle], expected_symbol="QQQ")

    with pytest.raises(BacktestCandleValidationError, match="timeframe"):
        validate_backtest_candles([candle], expected_timeframe="5m")


def _row() -> dict[str, object]:
    return {
        "symbol": "SPY",
        "ts_event": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        "session_date": date(2024, 1, 2),
        "timeframe": "1m",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000,
    }


def _candle(ts_event: datetime | None = None) -> BacktestCandle:
    ts_event = ts_event or datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    return BacktestCandle(
        symbol="SPY",
        ts_event=ts_event,
        session_date=(ts_event - timedelta()).date(),
        timeframe="1m",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000,
    )
