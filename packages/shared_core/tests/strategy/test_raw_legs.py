from datetime import UTC, date, datetime, timedelta

import pytest

from shared_core.backtesting import BacktestCandle, BacktestCandleValidationError
from shared_core.strategy.raw_legs import detect_raw_legs


def test_raw_leg_engine_starts_after_initial_reference_and_continues() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=99.8, low=99.2),
        _candle(2, high=100.5, low=99.4),
        _candle(3, high=101.0, low=99.8),
    ]

    legs = detect_raw_legs(candles, expected_symbol="SPY")

    assert len(legs) == 1
    leg = legs[0]
    assert leg.leg_direction == "up"
    assert leg.status == "active"
    assert leg.start_bar_time == candles[2].ts_event
    assert leg.start_price == 100.0
    assert leg.end_bar_time == candles[3].ts_event
    assert leg.bar_count == 2
    assert leg.leg_high_price == 101.0
    assert leg.leg_high_bar_time == candles[3].ts_event
    assert leg.leg_low_price == 99.4
    assert leg.leg_low_bar_time == candles[2].ts_event
    assert leg.switch_bar_time is None


def test_raw_leg_engine_switches_and_allows_one_candle_legs() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.5, low=99.4),
        _candle(2, high=100.4, low=99.2),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 2
    assert legs[0].leg_direction == "up"
    assert legs[0].status == "confirmed"
    assert legs[0].start_bar_time == candles[1].ts_event
    assert legs[0].end_bar_time == candles[1].ts_event
    assert legs[0].bar_count == 1
    assert legs[0].switch_bar_time == candles[2].ts_event

    assert legs[1].leg_direction == "down"
    assert legs[1].status == "active"
    assert legs[1].start_bar_time == candles[2].ts_event
    assert legs[1].start_price == 99.4
    assert legs[1].bar_count == 1


def test_raw_leg_engine_keeps_inside_and_equal_candles_in_active_leg() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.5, low=99.4),
        _candle(2, high=100.5, low=99.4),
        _candle(3, high=100.4, low=99.5),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].bar_count == 3
    assert legs[0].end_bar_time == candles[3].ts_event


def test_raw_leg_engine_waits_for_outside_bar_resolution_before_first_leg() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=101.0, low=98.0),
        _candle(2, high=100.5, low=98.5),
        _candle(3, high=101.5, low=98.4),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].status == "active"
    assert legs[0].start_bar_time == candles[3].ts_event
    assert legs[0].start_price == 101.0
    assert legs[0].bar_count == 1


def test_raw_leg_engine_expands_consecutive_outside_bars_before_first_leg() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=101.0, low=98.0),
        _candle(2, high=101.5, low=97.5),
        _candle(3, high=101.4, low=97.0),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "down"
    assert legs[0].start_bar_time == candles[3].ts_event
    assert legs[0].start_price == 97.5


def test_raw_leg_engine_switches_only_after_active_outside_bar_resolves() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.5, low=99.4),
        _candle(2, high=101.0, low=99.0),
        _candle(3, high=100.8, low=98.5),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 2
    assert legs[0].leg_direction == "up"
    assert legs[0].status == "confirmed"
    assert legs[0].end_bar_time == candles[2].ts_event
    assert legs[0].bar_count == 2
    assert legs[0].leg_high_price == 101.0
    assert legs[0].leg_low_price == 99.0
    assert legs[0].switch_bar_time == candles[3].ts_event

    assert legs[1].leg_direction == "down"
    assert legs[1].status == "active"
    assert legs[1].start_bar_time == candles[3].ts_event
    assert legs[1].start_price == 99.0


def test_raw_leg_engine_expands_consecutive_outside_bars_during_active_leg() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.5, low=99.4),
        _candle(2, high=101.0, low=99.0),
        _candle(3, high=101.5, low=98.5),
        _candle(4, high=101.4, low=98.0),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 2
    assert legs[0].leg_direction == "up"
    assert legs[0].bar_count == 3
    assert legs[0].leg_high_price == 101.5
    assert legs[0].leg_low_price == 98.5
    assert legs[0].switch_bar_time == candles[4].ts_event
    assert legs[1].leg_direction == "down"
    assert legs[1].start_price == 98.5


def test_raw_leg_engine_leaves_unresolved_pending_outside_bar_in_active_leg() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.5, low=99.4),
        _candle(2, high=101.0, low=99.0),
        _candle(3, high=100.9, low=99.1),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].status == "active"
    assert legs[0].bar_count == 3
    assert legs[0].leg_high_price == 101.0
    assert legs[0].leg_low_price == 99.0


def test_raw_leg_engine_equal_highs_and_lows_never_start_or_switch_legs() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.0, low=99.0),
        _candle(2, high=100.1, low=99.0),
        _candle(3, high=100.1, low=99.0),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].start_bar_time == candles[2].ts_event
    assert legs[0].bar_count == 2


def test_raw_leg_engine_tiny_wick_break_counts() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(1, high=100.0001, low=99.5),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].start_price == 100.0


def test_raw_leg_engine_gap_candles_follow_normal_break_rules() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        BacktestCandle(
            symbol="SPY",
            ts_event=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
            session_date=date(2024, 1, 2),
            timeframe="1m",
            open=100.8,
            high=101.0,
            low=100.7,
            close=100.9,
            volume=1000,
        ),
    ]

    legs = detect_raw_legs(candles)

    assert len(legs) == 1
    assert legs[0].leg_direction == "up"
    assert legs[0].start_price == 100.0


def test_raw_leg_engine_rejects_missing_one_minute_candles() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0),
        _candle(2, high=100.5, low=99.4),
    ]

    with pytest.raises(BacktestCandleValidationError, match="continuous"):
        detect_raw_legs(candles)


def test_raw_leg_engine_rejects_duplicate_timestamps() -> None:
    candle = _candle(0, high=100.0, low=99.0)

    with pytest.raises(BacktestCandleValidationError, match="duplicate"):
        detect_raw_legs([candle, candle])


def test_raw_leg_engine_rejects_out_of_order_candles() -> None:
    candles = [
        _candle(1, high=100.5, low=99.4),
        _candle(0, high=100.0, low=99.0),
    ]

    with pytest.raises(BacktestCandleValidationError, match="sorted"):
        detect_raw_legs(candles)


def test_raw_leg_engine_rejects_wrong_timeframe() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0, timeframe="5m"),
        _candle(1, high=100.5, low=99.4, timeframe="5m"),
    ]

    with pytest.raises(BacktestCandleValidationError, match="timeframe"):
        detect_raw_legs(candles)


def test_raw_leg_engine_rejects_wrong_symbol() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0, symbol="QQQ"),
        _candle(1, high=100.5, low=99.4, symbol="QQQ"),
    ]

    with pytest.raises(BacktestCandleValidationError, match="symbol"):
        detect_raw_legs(candles, expected_symbol="SPY")


def _candle(
    offset_minutes: int,
    *,
    high: float,
    low: float,
    symbol: str = "SPY",
    timeframe: str = "1m",
) -> BacktestCandle:
    ts_event = datetime(2024, 1, 2, 14, 30, tzinfo=UTC) + timedelta(minutes=offset_minutes)
    midpoint = (high + low) / 2
    return BacktestCandle(
        symbol=symbol,
        ts_event=ts_event,
        session_date=date(2024, 1, 2),
        timeframe=timeframe,
        open=midpoint,
        high=high,
        low=low,
        close=midpoint,
        volume=1000,
    )
