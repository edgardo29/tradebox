"""Backtest candle input contracts and validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

REQUIRED_CANDLE_COLUMNS = {
    "symbol",
    "ts_event",
    "session_date",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


class BacktestCandleValidationError(ValueError):
    """Raised when candle input data is invalid for backtesting."""


@dataclass(frozen=True)
class BacktestCandle:
    """Clean OHLCV candle used by the backtest runner."""

    symbol: str
    ts_event: datetime
    session_date: date
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_mapping(self) -> dict[str, object]:
        """Return a serializable mapping."""

        return {
            "symbol": self.symbol,
            "ts_event": self.ts_event,
            "session_date": self.session_date,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def backtest_candles_from_mappings(
    rows: Iterable[Mapping[str, Any]],
) -> list[BacktestCandle]:
    """Convert clean OHLCV row mappings into validated backtest candles."""

    candles = [_candle_from_mapping(row) for row in rows]
    validate_backtest_candles(candles)
    return candles


def validate_backtest_candles(
    candles: list[BacktestCandle],
    *,
    expected_symbol: str | None = None,
    expected_timeframe: str | None = None,
) -> None:
    """Validate clean candles before they are used by a backtest."""

    if not candles:
        raise BacktestCandleValidationError("Backtest candle data must not be empty.")

    expected_symbol = expected_symbol.upper() if expected_symbol is not None else None
    seen_keys: set[tuple[str, str, datetime]] = set()
    previous_ts = None

    for candle in candles:
        if not candle.symbol:
            raise BacktestCandleValidationError("Backtest candle symbol is required.")
        if expected_symbol is not None and candle.symbol != expected_symbol:
            raise BacktestCandleValidationError("Backtest candle symbol does not match config.")
        if not candle.timeframe:
            raise BacktestCandleValidationError("Backtest candle timeframe is required.")
        if expected_timeframe is not None and candle.timeframe != expected_timeframe:
            raise BacktestCandleValidationError("Backtest candle timeframe does not match config.")
        if candle.ts_event.tzinfo is None or candle.ts_event.utcoffset() != UTC.utcoffset(
            candle.ts_event
        ):
            raise BacktestCandleValidationError("Backtest candle ts_event must be UTC.")
        if candle.session_date != candle.ts_event.date():
            raise BacktestCandleValidationError("Backtest candle session_date must match ts_event.")
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            raise BacktestCandleValidationError("Backtest candle OHLC prices must be positive.")
        if candle.high < candle.low:
            raise BacktestCandleValidationError("Backtest candle high must be >= low.")
        if candle.high < candle.open or candle.high < candle.close:
            raise BacktestCandleValidationError("Backtest candle high must be >= open and close.")
        if candle.low > candle.open or candle.low > candle.close:
            raise BacktestCandleValidationError("Backtest candle low must be <= open and close.")
        if candle.volume < 0:
            raise BacktestCandleValidationError("Backtest candle volume must be non-negative.")

        key = (candle.symbol, candle.timeframe, candle.ts_event)
        if key in seen_keys:
            raise BacktestCandleValidationError("Backtest candles contain duplicate timestamps.")
        seen_keys.add(key)

        if previous_ts is not None and candle.ts_event < previous_ts:
            raise BacktestCandleValidationError("Backtest candle timestamps must be sorted.")
        previous_ts = candle.ts_event


def _candle_from_mapping(row: Mapping[str, Any]) -> BacktestCandle:
    missing = sorted(REQUIRED_CANDLE_COLUMNS - set(row))
    if missing:
        raise BacktestCandleValidationError(
            f"Backtest candle rows are missing required columns: {missing}"
        )

    return BacktestCandle(
        symbol=str(row["symbol"]).strip().upper(),
        ts_event=_parse_datetime(row["ts_event"]),
        session_date=_parse_date(row["session_date"]),
        timeframe=str(row["timeframe"]).strip(),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=int(row["volume"]),
    )


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise BacktestCandleValidationError("Backtest candle ts_event must be a datetime.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise BacktestCandleValidationError("Backtest candle session_date must be a date.")
