from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from shared_core.backtesting import (
    BacktestCandle,
    BacktestConfig,
    BacktestRunner,
    BacktestStrategyResult,
    NoOpStrategy,
)

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


def _config(strategy_name: str = "noop") -> BacktestConfig:
    return BacktestConfig.create(
        symbol="SPY",
        timeframe="1m",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        clean_data_partition_id=PARTITION_ID,
        strategy_name=strategy_name,
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
