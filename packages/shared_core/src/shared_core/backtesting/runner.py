"""Backtest runner skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared_core.backtesting.candles import BacktestCandle, validate_backtest_candles
from shared_core.backtesting.config import BacktestConfig
from shared_core.backtesting.strategy import (
    BacktestStrategy,
    BacktestStrategyResult,
    NoOpStrategy,
)


@dataclass(frozen=True)
class BacktestRunResult:
    """Structured backtest run result."""

    run_status: str
    strategy_name: str
    strategy_version: str
    candle_count: int
    detected_setups: list[dict[str, Any]]
    simulated_trades: list[dict[str, Any]]
    metrics: dict[str, Any]

    @property
    def detected_setup_count(self) -> int:
        """Number of detected setup outputs."""

        return len(self.detected_setups)

    @property
    def simulated_trade_count(self) -> int:
        """Number of simulated trade outputs."""

        return len(self.simulated_trades)


class BacktestRunner:
    """Minimal runner that executes a strategy against clean candles."""

    def __init__(self, strategy: BacktestStrategy | None = None) -> None:
        self.strategy = strategy or NoOpStrategy()

    def run(
        self,
        *,
        config: BacktestConfig,
        candles: list[BacktestCandle],
    ) -> BacktestRunResult:
        """Validate inputs, run the strategy, and return structured results."""

        validate_backtest_candles(
            candles,
            expected_symbol=config.symbol,
            expected_timeframe=config.timeframe,
        )
        strategy_result = self.strategy.run(config=config, candles=candles)
        return _to_run_result(
            strategy_result,
            strategy_name=self.strategy.name,
            strategy_version=self.strategy.version,
            candle_count=len(candles),
        )


def _to_run_result(
    strategy_result: BacktestStrategyResult,
    *,
    strategy_name: str,
    strategy_version: str,
    candle_count: int,
) -> BacktestRunResult:
    metrics = {
        **strategy_result.metrics,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "candle_count": candle_count,
        "detected_setup_count": len(strategy_result.detected_setups),
        "simulated_trade_count": len(strategy_result.simulated_trades),
    }
    return BacktestRunResult(
        run_status="succeeded",
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        candle_count=candle_count,
        detected_setups=strategy_result.detected_setups,
        simulated_trades=strategy_result.simulated_trades,
        metrics=metrics,
    )
