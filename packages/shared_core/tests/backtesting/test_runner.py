from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from shared_core.backtesting import (
    BacktestCandle,
    BacktestConfig,
    BacktestConfigError,
    BacktestRunner,
    BacktestStrategyResult,
    NoOpStrategy,
)
from shared_core.strategy.two_legged_pullback import TwoLeggedPullbackStrategy

PARTITION_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_noop_backtest_runner_succeeds_with_zero_trades() -> None:
    config = _config()
    result = BacktestRunner().run(config=config, candles=[_candle()])

    assert result.run_status == "succeeded"
    assert result.strategy_name == "noop"
    assert result.candle_count == 1
    assert result.detected_setup_count == 0
    assert result.simulated_trade_count == 0
    assert result.detected_setups == []
    assert result.simulated_trades == []
    assert result.metrics["candle_count"] == 1


def test_noop_strategy_direct_result_has_no_setups_or_trades() -> None:
    strategy = NoOpStrategy()

    result = strategy.run(config=_config(), candles=[_candle()])

    assert result.detected_setups == []
    assert result.simulated_trades == []


def test_runner_validates_candles_before_strategy_runs() -> None:
    with pytest.raises(Exception, match="symbol"):
        BacktestRunner().run(config=_config(), candles=[_candle(symbol="QQQ")])


def test_runner_requires_config_strategy_name_to_match_strategy() -> None:
    with pytest.raises(BacktestConfigError, match="strategy_name"):
        BacktestRunner().run(config=_config(strategy_name="other"), candles=[_candle()])


def test_runner_does_not_require_databento() -> None:
    class CountingStrategy:
        name = "counting"
        version = "0.1.0"

        def run(self, *, config: BacktestConfig, candles: list[BacktestCandle]):
            return BacktestStrategyResult(metrics={"called": True})

    result = BacktestRunner(strategy=CountingStrategy()).run(
        config=_config(strategy_name="counting"),
        candles=[_candle()],
    )

    assert result.metrics["called"] is True
    assert result.simulated_trade_count == 0


def test_runner_executes_two_legged_pullback_strategy() -> None:
    result = BacktestRunner(strategy=TwoLeggedPullbackStrategy()).run(
        config=_config(
            strategy_name="two_legged_pullback",
            parameters={
                "use_anchor_context": False,
                "use_ema_context": False,
                "use_min_anchor_range_filter": False,
                "use_raw_leg_chop_filter": False,
            },
        ),
        candles=_two_legged_pullback_candles(),
    )

    assert result.strategy_name == "two_legged_pullback"
    assert result.detected_setup_count == 1
    assert result.simulated_trade_count == 1
    assert result.detected_setups[0]["setup_status"] == "triggered"
    assert result.simulated_trades[0]["exit_reason"] == "target_hit"


def test_runner_skips_two_legged_pullback_when_required_context_is_missing() -> None:
    result = BacktestRunner(strategy=TwoLeggedPullbackStrategy()).run(
        config=_config(
            strategy_name="two_legged_pullback",
            parameters={"use_previous_day_level_filter": True},
            metadata={"instrument_id": "03b7aec1-249d-4a44-8833-f08f9248ff9a"},
        ),
        candles=[_candle()],
    )

    assert result.detected_setup_count == 0
    assert result.simulated_trade_count == 0
    assert result.metrics["skip_reason"] == "missing_required_context"
    assert result.metrics["skipped_symbol_days"] == [
        {
            "instrument_id": "03b7aec1-249d-4a44-8833-f08f9248ff9a",
            "symbol": "SPY",
            "trade_date": "2024-01-02",
            "reason": "missing_required_context",
            "missing_context": ["previous_day_levels"],
        }
    ]


def test_runner_skips_two_legged_pullback_when_analysis_window_is_incomplete() -> None:
    result = BacktestRunner(strategy=TwoLeggedPullbackStrategy()).run(
        config=_config(
            strategy_name="two_legged_pullback",
            parameters={"use_previous_day_level_filter": False},
            metadata={"instrument_id": "03b7aec1-249d-4a44-8833-f08f9248ff9a"},
        ),
        candles=[_candle()],
    )

    assert result.detected_setup_count == 0
    assert result.simulated_trade_count == 0
    assert result.metrics["skip_reason"] == "invalid_candle_data"
    assert result.metrics["skipped_symbol_days"] == [
        {
            "instrument_id": "03b7aec1-249d-4a44-8833-f08f9248ff9a",
            "symbol": "SPY",
            "trade_date": "2024-01-02",
            "reason": "invalid_candle_data",
            "missing_context": ["analysis_window_start"],
        }
    ]


def _config(
    strategy_name: str = "noop",
    *,
    parameters: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> BacktestConfig:
    return BacktestConfig.create(
        symbol="SPY",
        timeframe="1m",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        clean_data_partition_id=PARTITION_ID,
        strategy_name=strategy_name,
        parameters=parameters,
        metadata=metadata,
    )


def _candle(symbol: str = "SPY") -> BacktestCandle:
    return BacktestCandle(
        symbol=symbol,
        ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        session_date=date(2024, 1, 2),
        timeframe="1m",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000,
    )


def _two_legged_pullback_candles() -> list[BacktestCandle]:
    candles = [
        _strategy_candle(index, open_price=99.5, high=100.0, low=99.0, close=99.5)
        for index in range(480)
    ]
    pattern = [
        _strategy_candle(90, open_price=99.5, high=100.0, low=99.0, close=99.4),
        _strategy_candle(91, open_price=99.4, high=99.8, low=98.8, close=99.0),
        _strategy_candle(92, open_price=99.0, high=99.5, low=98.5, close=98.7),
        _strategy_candle(93, open_price=98.8, high=99.6, low=98.6, close=99.4),
        _strategy_candle(94, open_price=99.4, high=100.0, low=98.9, close=99.8),
        _strategy_candle(95, open_price=99.7, high=99.9, low=98.7, close=99.0),
        _strategy_candle(96, open_price=99.0, high=99.8, low=98.4, close=98.8),
        _strategy_candle(97, open_price=99.6, high=99.9, low=99.5, close=99.8),
        _strategy_candle(98, open_price=99.9, high=100.1, low=99.7, close=100.0),
        _strategy_candle(99, open_price=100.0, high=100.8, low=99.9, close=100.7),
    ]
    candles[90:100] = pattern
    for index in range(100, len(candles)):
        candles[index] = _strategy_candle(
            index,
            open_price=100.1,
            high=100.8,
            low=99.9,
            close=100.1,
        )
    return candles


def _strategy_candle(
    offset_minutes: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> BacktestCandle:
    return BacktestCandle(
        symbol="SPY",
        ts_event=datetime(2024, 1, 2, 13, 0, tzinfo=UTC) + timedelta(minutes=offset_minutes),
        session_date=date(2024, 1, 2),
        timeframe="1m",
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )
