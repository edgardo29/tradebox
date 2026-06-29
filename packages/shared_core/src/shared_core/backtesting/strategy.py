"""Backtest strategy interfaces and placeholder implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from shared_core.backtesting.candles import BacktestCandle, validate_backtest_candles
from shared_core.backtesting.config import BacktestConfig


@dataclass(frozen=True)
class BacktestStrategyResult:
    """Structured strategy output before persistence."""

    detected_setups: list[dict[str, Any]] = field(default_factory=list)
    simulated_trades: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class BacktestStrategy(Protocol):
    """Strategy interface used by the backtest runner."""

    name: str
    version: str

    def run(
        self,
        *,
        config: BacktestConfig,
        candles: list[BacktestCandle],
    ) -> BacktestStrategyResult: ...


@dataclass(frozen=True)
class NoOpStrategy:
    """Placeholder strategy that intentionally produces no trades."""

    name: str = "noop"
    version: str = "0.1.0"

    def run(
        self,
        *,
        config: BacktestConfig,
        candles: list[BacktestCandle],
    ) -> BacktestStrategyResult:
        """Validate candles and return a successful zero-trade result."""

        validate_backtest_candles(
            candles,
            expected_symbol=config.symbol,
            expected_timeframe=config.timeframe,
        )
        return BacktestStrategyResult(
            detected_setups=[],
            simulated_trades=[],
            metrics={
                "strategy_name": self.name,
                "strategy_version": self.version,
                "candle_count": len(candles),
                "detected_setup_count": 0,
                "simulated_trade_count": 0,
            },
        )
