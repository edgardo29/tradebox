"""Raw one-minute leg detection for strategy setup logic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from shared_core.backtesting.candles import (
    BacktestCandle,
    BacktestCandleValidationError,
    validate_backtest_candles,
)

RawLegDirection = Literal["up", "down"]
RawLegStatus = Literal["active", "confirmed"]
_BreakDirection = RawLegDirection | Literal["outside"] | None


@dataclass(frozen=True)
class RawLeg:
    """A mechanical raw price leg built from one-minute candles."""

    leg_direction: RawLegDirection
    status: RawLegStatus
    start_bar_time: datetime
    start_price: float
    end_bar_time: datetime
    bar_count: int
    leg_high_price: float
    leg_high_bar_time: datetime
    leg_low_price: float
    leg_low_bar_time: datetime
    switch_bar_time: datetime | None = None


def detect_raw_legs(
    candles: Sequence[BacktestCandle],
    *,
    expected_symbol: str | None = None,
) -> list[RawLeg]:
    """Detect raw up/down legs from continuous one-minute candles.

    The caller owns session filtering. The first candle in ``candles`` is treated as the
    initial raw-leg reference candle.
    """

    candle_list = list(candles)
    validate_backtest_candles(
        candle_list,
        expected_symbol=expected_symbol,
        expected_timeframe="1m",
    )
    _validate_continuous_one_minute_candles(candle_list)

    if len(candle_list) < 2:
        return []

    legs: list[RawLeg] = []
    active_leg: _RawLegAccumulator | None = None
    pending_outside_bar: _PendingOutsideBar | None = None
    initial_reference = candle_list[0]

    for index in range(1, len(candle_list)):
        previous = candle_list[index - 1]
        current = candle_list[index]

        if pending_outside_bar is not None:
            resolution = _break_direction(
                current,
                reference_high=pending_outside_bar.high,
                reference_low=pending_outside_bar.low,
            )
            if resolution == "outside":
                active_leg = _include_pending_candle(active_leg, current)
                pending_outside_bar.expand(current)
                continue
            if resolution is None:
                active_leg = _include_pending_candle(active_leg, current)
                continue

            start_price = _start_price_for_resolution(resolution, pending_outside_bar)
            active_leg = _apply_directional_break(
                legs,
                active_leg=active_leg,
                current=current,
                direction=resolution,
                start_price=start_price,
            )
            pending_outside_bar = None
            continue

        if active_leg is None:
            direction = _break_direction(
                current,
                reference_high=initial_reference.high,
                reference_low=initial_reference.low,
            )
            reference_high = initial_reference.high
            reference_low = initial_reference.low
        else:
            direction = _break_direction(
                current,
                reference_high=previous.high,
                reference_low=previous.low,
            )
            reference_high = previous.high
            reference_low = previous.low

        if direction == "outside":
            active_leg = _include_pending_candle(active_leg, current)
            pending_outside_bar = _PendingOutsideBar(high=current.high, low=current.low)
            continue
        if direction is None:
            if active_leg is not None:
                active_leg.include_candle(current)
            continue

        start_price = reference_high if direction == "up" else reference_low
        active_leg = _apply_directional_break(
            legs,
            active_leg=active_leg,
            current=current,
            direction=direction,
            start_price=start_price,
        )

    if active_leg is not None:
        legs.append(active_leg.to_raw_leg(status="active"))

    return legs


@dataclass
class _PendingOutsideBar:
    high: float
    low: float

    def expand(self, candle: BacktestCandle) -> None:
        self.high = max(self.high, candle.high)
        self.low = min(self.low, candle.low)


@dataclass
class _RawLegAccumulator:
    leg_direction: RawLegDirection
    start_bar_time: datetime
    start_price: float
    end_bar_time: datetime
    bar_count: int
    leg_high_price: float
    leg_high_bar_time: datetime
    leg_low_price: float
    leg_low_bar_time: datetime

    @classmethod
    def start(
        cls,
        *,
        direction: RawLegDirection,
        start_price: float,
        candle: BacktestCandle,
    ) -> _RawLegAccumulator:
        return cls(
            leg_direction=direction,
            start_bar_time=candle.ts_event,
            start_price=start_price,
            end_bar_time=candle.ts_event,
            bar_count=1,
            leg_high_price=candle.high,
            leg_high_bar_time=candle.ts_event,
            leg_low_price=candle.low,
            leg_low_bar_time=candle.ts_event,
        )

    def include_candle(self, candle: BacktestCandle) -> None:
        self.end_bar_time = candle.ts_event
        self.bar_count += 1
        if candle.high > self.leg_high_price:
            self.leg_high_price = candle.high
            self.leg_high_bar_time = candle.ts_event
        if candle.low < self.leg_low_price:
            self.leg_low_price = candle.low
            self.leg_low_bar_time = candle.ts_event

    def to_raw_leg(
        self,
        *,
        status: RawLegStatus,
        switch_bar_time: datetime | None = None,
    ) -> RawLeg:
        return RawLeg(
            leg_direction=self.leg_direction,
            status=status,
            start_bar_time=self.start_bar_time,
            start_price=self.start_price,
            end_bar_time=self.end_bar_time,
            bar_count=self.bar_count,
            leg_high_price=self.leg_high_price,
            leg_high_bar_time=self.leg_high_bar_time,
            leg_low_price=self.leg_low_price,
            leg_low_bar_time=self.leg_low_bar_time,
            switch_bar_time=switch_bar_time,
        )


def _apply_directional_break(
    legs: list[RawLeg],
    *,
    active_leg: _RawLegAccumulator | None,
    current: BacktestCandle,
    direction: RawLegDirection,
    start_price: float,
) -> _RawLegAccumulator:
    if active_leg is None:
        return _RawLegAccumulator.start(
            direction=direction,
            start_price=start_price,
            candle=current,
        )
    if active_leg.leg_direction == direction:
        active_leg.include_candle(current)
        return active_leg

    legs.append(active_leg.to_raw_leg(status="confirmed", switch_bar_time=current.ts_event))
    return _RawLegAccumulator.start(
        direction=direction,
        start_price=start_price,
        candle=current,
    )


def _break_direction(
    candle: BacktestCandle,
    *,
    reference_high: float,
    reference_low: float,
) -> _BreakDirection:
    up_break = candle.high > reference_high
    down_break = candle.low < reference_low

    if up_break and down_break:
        return "outside"
    if up_break:
        return "up"
    if down_break:
        return "down"
    return None


def _include_pending_candle(
    active_leg: _RawLegAccumulator | None,
    candle: BacktestCandle,
) -> _RawLegAccumulator | None:
    if active_leg is not None:
        active_leg.include_candle(candle)
    return active_leg


def _start_price_for_resolution(
    resolution: RawLegDirection,
    pending_outside_bar: _PendingOutsideBar,
) -> float:
    return pending_outside_bar.high if resolution == "up" else pending_outside_bar.low


def _validate_continuous_one_minute_candles(candles: Sequence[BacktestCandle]) -> None:
    for previous, current in zip(candles, candles[1:], strict=False):
        if current.ts_event != previous.ts_event + timedelta(minutes=1):
            raise BacktestCandleValidationError(
                "Raw leg candles must be continuous one-minute bars."
            )
