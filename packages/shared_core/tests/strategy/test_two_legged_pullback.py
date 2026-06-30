from datetime import UTC, date, datetime, timedelta
from typing import Literal

import pytest

from shared_core.backtesting import BacktestCandle, BacktestCandleValidationError
from shared_core.strategy.raw_legs import RawLeg, RawLegDirection, RawLegStatus
from shared_core.strategy.two_legged_pullback import (
    AnchorRange,
    PlannedTradeLevels,
    PremarketLevels,
    StructuralSwing,
    TwoLeggedPullbackConfig,
    TwoLeggedPullbackContext,
    build_anchor_ranges,
    build_detected_setup_payload,
    build_two_legged_pullback_context,
    detect_structural_swings,
    detect_two_legged_pullback_structures,
    evaluate_setup_filters,
    find_signal_bar_for_structure,
    planned_trade_levels,
    qualify_signal_bar,
    simulate_entry_and_trade,
)

TestSetupSide = Literal["long", "short"]


def test_structural_swing_high_uses_three_left_and_three_right_bars() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[100.0, 101.0, 102.0, 105.0, 103.0, 102.0, 101.0],
        lows=[99.0, 99.2, 99.4, 99.6, 99.5, 99.3, 99.1],
    )

    swings = detect_structural_swings(candles)

    assert swings == [
        StructuralSwing(
            kind="high",
            price=105.0,
            pivot_bar_time=candles[3].ts_event,
            confirmed_at=candles[6].ts_event,
            pivot_index=3,
        )
    ]


def test_structural_swing_low_uses_three_left_and_three_right_bars() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[101.0, 101.2, 101.4, 101.3, 101.5, 101.3, 101.1],
        lows=[100.0, 99.0, 98.0, 95.0, 97.0, 98.0, 99.0],
    )

    swings = detect_structural_swings(candles)

    assert swings == [
        StructuralSwing(
            kind="low",
            price=95.0,
            pivot_bar_time=candles[3].ts_event,
            confirmed_at=candles[6].ts_event,
            pivot_index=3,
        )
    ]


def test_raw_leg_extreme_is_not_automatically_a_structural_swing() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[100.0, 104.0, 103.0, 102.0, 105.0, 103.0, 102.0],
        lows=[99.0, 99.2, 99.4, 99.6, 99.8, 99.7, 99.5],
    )

    swings = detect_structural_swings(candles)

    assert swings == []


def test_structural_swing_requires_right_side_confirmation() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[100.0, 101.0, 102.0, 105.0, 103.0, 102.0],
        lows=[99.0, 99.2, 99.4, 99.6, 99.5, 99.3],
    )

    assert detect_structural_swings(candles) == []


def test_structural_swing_equal_highs_and_lows_do_not_confirm() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[100.0, 101.0, 105.0, 105.0, 104.0, 103.0, 102.0],
        lows=[100.0, 99.0, 95.0, 95.0, 96.0, 97.0, 98.0],
    )

    assert detect_structural_swings(candles) == []


def test_structural_swing_uses_configurable_left_and_right_bars() -> None:
    candles = _candles_from_highs_and_lows(
        highs=[100.0, 101.0, 105.0, 103.0],
        lows=[99.0, 99.2, 99.4, 99.3],
    )

    swings = detect_structural_swings(candles, left_bars=2, right_bars=1)

    assert swings == [
        StructuralSwing(
            kind="high",
            price=105.0,
            pivot_bar_time=candles[2].ts_event,
            confirmed_at=candles[3].ts_event,
            pivot_index=2,
        )
    ]


def test_structural_swing_rejects_invalid_candle_data() -> None:
    candles = [
        _candle(0, high=100.0, low=99.0, timeframe="5m"),
        _candle(1, high=101.0, low=99.5, timeframe="5m"),
    ]

    with pytest.raises(BacktestCandleValidationError, match="timeframe"):
        detect_structural_swings(candles)


def test_anchor_ranges_use_prior_opposite_structural_swing() -> None:
    low = StructuralSwing(
        kind="low",
        price=99.0,
        pivot_bar_time=_time(0),
        confirmed_at=_time(3),
        pivot_index=0,
    )
    high = StructuralSwing(
        kind="high",
        price=102.0,
        pivot_bar_time=_time(5),
        confirmed_at=_time(8),
        pivot_index=5,
    )
    next_low = StructuralSwing(
        kind="low",
        price=100.0,
        pivot_bar_time=_time(10),
        confirmed_at=_time(13),
        pivot_index=10,
    )

    anchors = build_anchor_ranges([low, high, next_low])

    assert len(anchors) == 2
    assert anchors[0].side == "long"
    assert anchors[0].anchor_low == 99.0
    assert anchors[0].anchor_low_time == low.pivot_bar_time
    assert anchors[0].anchor_high == 102.0
    assert anchors[0].anchor_high_time == high.pivot_bar_time

    assert anchors[1].side == "short"
    assert anchors[1].anchor_high == 102.0
    assert anchors[1].anchor_high_time == high.pivot_bar_time
    assert anchors[1].anchor_low == 100.0
    assert anchors[1].anchor_low_time == next_low.pivot_bar_time


def test_anchor_ranges_skip_invalid_or_flat_ranges() -> None:
    low_above_high = StructuralSwing(
        kind="low",
        price=103.0,
        pivot_bar_time=_time(0),
        confirmed_at=_time(3),
        pivot_index=0,
    )
    high_below_low = StructuralSwing(
        kind="high",
        price=102.0,
        pivot_bar_time=_time(5),
        confirmed_at=_time(8),
        pivot_index=5,
    )
    flat_low = StructuralSwing(
        kind="low",
        price=102.0,
        pivot_bar_time=_time(10),
        confirmed_at=_time(13),
        pivot_index=10,
    )

    assert build_anchor_ranges([low_above_high, high_below_low]) == []
    assert build_anchor_ranges([high_below_low, flat_low]) == []


def test_two_legged_structure_detects_valid_long_with_active_leg2() -> None:
    anchor = _anchor("long", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("up", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]

    structures = detect_two_legged_pullback_structures(raw_legs, [anchor])

    assert len(structures) == 1
    assert structures[0].side == "long"
    assert structures[0].anchor == anchor
    assert structures[0].leg1 == raw_legs[0]
    assert structures[0].middle_move == raw_legs[1]
    assert structures[0].leg2 == raw_legs[2]


def test_two_legged_structure_detects_valid_short_with_confirmed_leg2() -> None:
    anchor = _anchor("short", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("up", "confirmed", 1, high=101.5, low=99.5),
        _leg("down", "confirmed", 2, high=101.2, low=100.0),
        _leg("up", "confirmed", 3, high=102.5, low=100.5),
    ]

    structures = detect_two_legged_pullback_structures(raw_legs, [anchor])

    assert len(structures) == 1
    assert structures[0].side == "short"
    assert structures[0].anchor == anchor


def test_two_legged_structure_requires_confirmed_leg1_and_middle_move() -> None:
    anchor = _anchor("long", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("down", "active", 1, high=102.5, low=100.0),
        _leg("up", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]

    structures = detect_two_legged_pullback_structures(raw_legs, [anchor])

    assert structures == []


def test_two_legged_structure_rejects_active_middle_move() -> None:
    anchor = _anchor("long", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("up", "active", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]

    assert detect_two_legged_pullback_structures(raw_legs, [anchor]) == []


def test_two_legged_structure_rejects_wrong_direction_sequence() -> None:
    anchor = _anchor("long", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("down", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]

    assert detect_two_legged_pullback_structures(raw_legs, [anchor]) == []


def test_two_legged_structure_requires_anchor_when_anchor_context_is_on() -> None:
    raw_legs = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("up", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]

    assert detect_two_legged_pullback_structures(raw_legs, []) == []
    assert len(detect_two_legged_pullback_structures(raw_legs, [], use_anchor_context=False)) == 1


def test_two_legged_structure_ignores_anchors_when_anchor_context_is_off() -> None:
    anchor = _anchor("long", anchor_low=100.0, anchor_high=101.0)
    raw_legs = [
        _leg("down", "confirmed", 1, high=102.5, low=99.5),
        _leg("up", "confirmed", 2, high=101.8, low=99.6),
        _leg("down", "active", 3, high=101.5, low=99.4),
    ]

    assert detect_two_legged_pullback_structures(raw_legs, [anchor]) == []

    structures = detect_two_legged_pullback_structures(
        raw_legs,
        [anchor],
        use_anchor_context=False,
    )

    assert len(structures) == 1
    assert structures[0].anchor == anchor


def test_two_legged_structure_rejects_anchor_range_breaks_before_entry() -> None:
    anchor = _anchor("short", anchor_low=99.0, anchor_high=103.0)
    raw_legs = [
        _leg("up", "confirmed", 1, high=101.5, low=99.5),
        _leg("down", "confirmed", 2, high=101.2, low=100.0),
        _leg("up", "active", 3, high=103.1, low=100.5),
    ]

    structures = detect_two_legged_pullback_structures(raw_legs, [anchor])

    assert structures == []


def test_two_legged_structure_allows_leg2_extremes_inside_anchor_range() -> None:
    anchor = _anchor("long", anchor_low=99.0, anchor_high=103.0)
    lower_low_than_leg1 = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("up", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=99.5),
    ]
    equal_low_to_leg1 = [
        _leg("down", "confirmed", 1, high=102.5, low=100.0),
        _leg("up", "confirmed", 2, high=101.8, low=100.2),
        _leg("down", "active", 3, high=101.5, low=100.0),
    ]

    assert len(detect_two_legged_pullback_structures(lower_low_than_leg1, [anchor])) == 1
    assert len(detect_two_legged_pullback_structures(equal_low_to_leg1, [anchor])) == 1


def test_two_legged_structure_allows_short_leg2_extremes_inside_anchor_range() -> None:
    anchor = _anchor("short", anchor_low=99.0, anchor_high=103.0)
    lower_high_than_leg1 = [
        _leg("up", "confirmed", 1, high=101.5, low=99.5),
        _leg("down", "confirmed", 2, high=101.2, low=100.0),
        _leg("up", "active", 3, high=101.0, low=100.5),
    ]
    equal_high_to_leg1 = [
        _leg("up", "confirmed", 1, high=101.5, low=99.5),
        _leg("down", "confirmed", 2, high=101.2, low=100.0),
        _leg("up", "active", 3, high=101.5, low=100.5),
    ]
    higher_high_than_leg1 = [
        _leg("up", "confirmed", 1, high=101.5, low=99.5),
        _leg("down", "confirmed", 2, high=101.2, low=100.0),
        _leg("up", "active", 3, high=102.5, low=100.5),
    ]

    assert len(detect_two_legged_pullback_structures(lower_high_than_leg1, [anchor])) == 1
    assert len(detect_two_legged_pullback_structures(equal_high_to_leg1, [anchor])) == 1
    assert len(detect_two_legged_pullback_structures(higher_high_than_leg1, [anchor])) == 1


def test_two_legged_structure_uses_latest_valid_prior_anchor() -> None:
    old_anchor = AnchorRange(
        side="long",
        anchor_high=103.0,
        anchor_high_time=_time(1),
        anchor_low=99.0,
        anchor_low_time=_time(0),
    )
    latest_anchor = AnchorRange(
        side="long",
        anchor_high=102.0,
        anchor_high_time=_time(4),
        anchor_low=99.0,
        anchor_low_time=_time(2),
    )
    raw_legs = [
        _leg("down", "confirmed", 5, high=101.5, low=100.0),
        _leg("up", "confirmed", 6, high=101.8, low=100.2),
        _leg("down", "active", 7, high=101.5, low=99.5),
    ]

    structures = detect_two_legged_pullback_structures(
        raw_legs,
        [old_anchor, latest_anchor],
    )

    assert len(structures) == 1
    assert structures[0].anchor == latest_anchor


def test_two_legged_pullback_config_uses_v1_defaults_and_parameters() -> None:
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "target_r_multiple": "1.5",
            "previous_day_levels": {
                "high": "103.0",
                "low": "99.0",
                "close": "101.0",
            },
        }
    )

    assert config.use_anchor_context is True
    assert config.use_ema_context is False
    assert config.use_vwap_context is False
    assert config.entry_trigger_wait_bars == 1
    assert config.target_r_multiple == 1.5
    assert config.previous_day_levels == {
        "high": 103.0,
        "low": 99.0,
        "close": 101.0,
    }


def test_two_legged_pullback_config_rejects_invalid_parameters() -> None:
    invalid_parameters = [
        {"swing_left_bars": 0},
        {"entry_trigger_wait_bars": 0},
        {"ema_length": 0},
        {"target_r_multiple": 0},
        {"entry_break_buffer": -0.01},
        {"max_raw_leg_switches": -1},
    ]

    for parameters in invalid_parameters:
        with pytest.raises(ValueError):
            TwoLeggedPullbackConfig.from_parameters(parameters)


def test_context_records_skip_when_previous_day_filter_requires_missing_levels() -> None:
    config = TwoLeggedPullbackConfig.from_parameters({"use_previous_day_level_filter": True})

    context = build_two_legged_pullback_context(
        [_candle(0, high=100.0, low=99.0)],
        config=config,
        symbol="spy",
        instrument_id="03b7aec1-249d-4a44-8833-f08f9248ff9a",
    )

    assert context.should_skip_symbol_day is True
    assert context.skipped_symbol_days == [
        {
            "instrument_id": "03b7aec1-249d-4a44-8833-f08f9248ff9a",
            "symbol": "SPY",
            "trade_date": "2024-01-02",
            "reason": "missing_required_context",
            "missing_context": ["previous_day_levels"],
        }
    ]


def test_context_calculates_ema_vwap_and_premarket_levels() -> None:
    config = TwoLeggedPullbackConfig.from_parameters({"ema_length": 3})
    candles = [
        _candle_at(datetime(2024, 1, 2, 13, 0, tzinfo=UTC), high=100.0, low=99.0),
        _candle_at(datetime(2024, 1, 2, 13, 1, tzinfo=UTC), high=101.0, low=98.0),
        _candle_at(datetime(2024, 1, 2, 14, 30, tzinfo=UTC), high=102.0, low=100.0),
    ]

    context = build_two_legged_pullback_context(
        candles,
        config=config,
        symbol="SPY",
    )

    assert context.ema_by_time[candles[0].ts_event] == 99.5
    assert context.ema_by_time[candles[1].ts_event] == 99.5
    assert context.ema_by_time[candles[2].ts_event] == 100.25
    assert round(context.vwap_by_time[candles[2].ts_event], 6) == 100.0
    assert context.premarket_levels == PremarketLevels(high=101.0, low=98.0)


def test_context_ignores_candles_outside_analysis_window() -> None:
    config = TwoLeggedPullbackConfig.from_parameters({"ema_length": 3})
    outside_window = _candle_at(
        datetime(2024, 1, 2, 12, 59, tzinfo=UTC),
        high=500.0,
        low=499.0,
    )
    candles = [
        outside_window,
        _candle_at(datetime(2024, 1, 2, 13, 0, tzinfo=UTC), high=100.0, low=99.0),
        _candle_at(datetime(2024, 1, 2, 13, 1, tzinfo=UTC), high=101.0, low=98.0),
        _candle_at(datetime(2024, 1, 2, 14, 30, tzinfo=UTC), high=102.0, low=100.0),
    ]

    context = build_two_legged_pullback_context(candles, config=config, symbol="SPY")

    assert outside_window.ts_event not in context.ema_by_time
    assert context.ema_by_time[candles[1].ts_event] == 99.5
    assert context.ema_by_time[candles[2].ts_event] == 99.5
    assert context.ema_by_time[candles[3].ts_event] == 100.25
    assert round(context.vwap_by_time[candles[3].ts_event], 6) == 100.0


def test_signal_bar_rules_accept_long_momentum_and_rejection_bars() -> None:
    momentum = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=101.0, low=99.8, close=100.8),
    )
    rejection = qualify_signal_bar(
        "long",
        _custom_candle(21, open_price=99.9, high=100.8, low=99.0, close=100.4),
    )

    assert momentum is not None
    assert momentum.signal_type == "momentum"
    assert rejection is not None
    assert rejection.signal_type == "rejection"


def test_signal_bar_rules_accept_short_momentum_and_rejection_bars() -> None:
    momentum = qualify_signal_bar(
        "short",
        _custom_candle(20, open_price=100.8, high=101.0, low=99.8, close=100.0),
    )
    rejection = qualify_signal_bar(
        "short",
        _custom_candle(21, open_price=100.1, high=101.0, low=99.2, close=99.6),
    )

    assert momentum is not None
    assert momentum.signal_type == "momentum"
    assert rejection is not None
    assert rejection.signal_type == "rejection"


def test_signal_bar_rules_reject_weak_or_outside_anchor_bars() -> None:
    weak = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.7, close=100.05),
    )
    outside_anchor = qualify_signal_bar(
        "long",
        _custom_candle(21, open_price=100.0, high=101.0, low=98.9, close=100.8),
        anchor=_anchor("long", anchor_low=99.0, anchor_high=101.5),
    )

    assert weak is None
    assert outside_anchor is None


def test_signal_bar_can_be_leg2_switch_bar() -> None:
    candles = [
        _candle(0, high=102.0, low=101.0),
        _custom_candle(1, open_price=100.0, high=101.0, low=99.8, close=100.8),
    ]
    structure = _structure(
        "long",
        leg2=_leg(
            "down",
            "confirmed",
            0,
            high=101.5,
            low=99.8,
        ),
    )
    signal = find_signal_bar_for_structure(structure, candles, config=TwoLeggedPullbackConfig())

    assert signal is not None
    assert signal.candle == candles[1]


def test_signal_bar_scans_after_active_leg2_starts() -> None:
    candles = [
        _candle(0, high=101.5, low=99.8),
        _custom_candle(1, open_price=100.0, high=100.2, low=99.6, close=99.8),
        _custom_candle(2, open_price=99.8, high=100.4, low=99.7, close=100.3),
    ]
    structure = _structure(
        "long",
        leg2=_leg("down", "active", 0, high=101.5, low=99.8),
    )

    signal = find_signal_bar_for_structure(structure, candles, config=TwoLeggedPullbackConfig())

    assert signal is not None
    assert signal.candle == candles[2]


def test_planned_trade_levels_use_signal_bar_break_and_default_two_r_target() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=101.0, low=99.8, close=100.8),
    )
    assert signal is not None

    levels = planned_trade_levels(signal, config=TwoLeggedPullbackConfig())

    assert levels == PlannedTradeLevels(
        entry_price=101.01,
        stop_price=99.79,
        target_price=103.45,
        risk_per_share=1.22,
    )


def test_planned_trade_levels_use_short_signal_bar_break() -> None:
    signal = _short_signal()
    assert signal is not None

    levels = planned_trade_levels(signal, config=TwoLeggedPullbackConfig())

    assert levels == PlannedTradeLevels(
        entry_price=99.99,
        stop_price=100.51,
        target_price=98.95,
        risk_per_share=0.52,
    )


def test_setup_filters_accept_or_reject_ema_context() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.3, low=99.95))
    context = TwoLeggedPullbackContext(
        ema_by_time={signal.candle.ts_event: 100.0},
        vwap_by_time={signal.candle.ts_event: 100.0},
        previous_day_levels=None,
        premarket_levels=None,
        skipped_symbol_days=[],
    )

    passing = evaluate_setup_filters(
        structure,
        signal,
        context,
        [structure.leg1, structure.middle_move, structure.leg2],
        config=TwoLeggedPullbackConfig(),
    )
    failing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={signal.candle.ts_event: 101.0},
            vwap_by_time={signal.candle.ts_event: 100.0},
            previous_day_levels=None,
            premarket_levels=None,
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=TwoLeggedPullbackConfig(),
    )

    assert passing.passed is True
    assert failing.passed is False
    assert failing.rejection_reason == "ema_context_failed"


def test_setup_filters_record_filtered_out_reason_and_payload_metadata() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    config = TwoLeggedPullbackConfig.from_parameters({"min_anchor_range": 2.0})
    structure = _structure(
        "long",
        anchor=_anchor("long", anchor_low=99.5, anchor_high=101.0),
        leg2=_leg("down", "active", 19, high=100.3, low=99.95),
    )
    context = TwoLeggedPullbackContext(
        ema_by_time={signal.candle.ts_event: 100.0},
        vwap_by_time={signal.candle.ts_event: 100.0},
        previous_day_levels={"high": 101.0, "low": 99.0, "close": 100.0},
        premarket_levels=PremarketLevels(high=101.0, low=99.0),
        skipped_symbol_days=[],
    )

    filter_result = evaluate_setup_filters(
        structure,
        signal,
        context,
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )
    levels = planned_trade_levels(signal, config=config)
    payload = build_detected_setup_payload(
        structure,
        signal,
        levels,
        filter_result,
        config=config,
        context=context,
        setup_status="filtered_out",
        symbol="SPY",
    )

    assert filter_result.passed is False
    assert payload["setup_status"] == "filtered_out"
    assert payload["rejection_reason"] == "anchor_range_too_small"
    metadata = payload["setup_metadata_json"]
    assert metadata["filters"]["anchor_range"]["passed"] is False
    assert metadata["planned_trade"]["entry_price"] == levels.entry_price


def test_setup_filters_ignore_anchor_range_when_anchor_context_is_off() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure(
        "long",
        anchor=_anchor("long", anchor_low=99.0, anchor_high=101.5),
    )
    context = TwoLeggedPullbackContext(
        ema_by_time={signal.candle.ts_event: 100.0},
        vwap_by_time={signal.candle.ts_event: 100.0},
        previous_day_levels=None,
        premarket_levels=None,
        skipped_symbol_days=[],
    )
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_anchor_context": False,
            "use_ema_context": False,
            "use_raw_leg_chop_filter": False,
            "min_anchor_range": 3.0,
        }
    )

    result = evaluate_setup_filters(
        structure,
        signal,
        context,
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )

    assert result.passed is True
    assert "anchor_range" not in result.details


def test_setup_filters_accept_or_reject_vwap_context() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.3, low=99.95))
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "use_vwap_context": True,
            "use_raw_leg_chop_filter": False,
        }
    )

    passing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={signal.candle.ts_event: 100.0},
            previous_day_levels=None,
            premarket_levels=None,
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )
    failing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={signal.candle.ts_event: 101.0},
            previous_day_levels=None,
            premarket_levels=None,
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )

    assert passing.passed is True
    assert failing.passed is False
    assert failing.rejection_reason == "vwap_context_failed"


def test_setup_filters_accept_or_reject_previous_day_level_context() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.3, low=99.95))
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "use_previous_day_level_filter": True,
            "use_raw_leg_chop_filter": False,
        }
    )

    passing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={},
            previous_day_levels={"high": 100.0, "low": 98.0, "close": 99.0},
            premarket_levels=None,
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )
    failing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={},
            previous_day_levels={"high": 110.0, "low": 108.0, "close": 109.0},
            premarket_levels=None,
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )

    assert passing.passed is True
    assert failing.passed is False
    assert failing.rejection_reason == "previous_day_level_context_failed"


def test_setup_filters_accept_or_reject_premarket_level_context() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.3, low=99.95))
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "use_premarket_level_filter": True,
            "use_raw_leg_chop_filter": False,
        }
    )

    passing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={},
            previous_day_levels=None,
            premarket_levels=PremarketLevels(high=100.0, low=98.0),
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )
    failing = evaluate_setup_filters(
        structure,
        signal,
        TwoLeggedPullbackContext(
            ema_by_time={},
            vwap_by_time={},
            previous_day_levels=None,
            premarket_levels=PremarketLevels(high=110.0, low=108.0),
            skipped_symbol_days=[],
        ),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )

    assert passing.passed is True
    assert failing.passed is False
    assert failing.rejection_reason == "premarket_level_context_failed"


def test_setup_filters_raw_leg_chop_can_block_setup() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.3, low=99.9, close=100.25),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.3, low=99.95))
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "use_raw_leg_chop_filter": True,
            "max_raw_leg_switches": 1,
        }
    )
    raw_legs = [
        _leg("down", "confirmed", 16, high=100.2, low=99.8),
        _leg("up", "confirmed", 18, high=100.3, low=99.9),
        structure.leg2,
    ]

    result = evaluate_setup_filters(structure, signal, _empty_context(), raw_legs, config=config)

    assert result.passed is False
    assert result.rejection_reason == "raw_leg_chop"


def test_setup_filters_signal_bar_range_filter_can_be_disabled() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=100.0, high=100.04, low=100.0, close=100.04),
    )
    assert signal is not None
    structure = _structure("long", leg2=_leg("down", "active", 19, high=100.03, low=100.0))
    config = TwoLeggedPullbackConfig.from_parameters(
        {
            "use_ema_context": False,
            "use_min_signal_bar_range_filter": False,
            "use_raw_leg_chop_filter": False,
        }
    )

    result = evaluate_setup_filters(
        structure,
        signal,
        _empty_context(),
        [structure.leg1, structure.middle_move, structure.leg2],
        config=config,
    )

    assert result.passed is True
    assert "signal_bar_range" not in result.details


def test_trade_simulation_triggers_entry_and_hits_target() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()
    levels = planned_trade_levels(signal, config=config)
    candles = [
        signal.candle,
        _custom_candle(21, open_price=100.0, high=100.2, low=99.8, close=100.1),
        _custom_candle(22, open_price=100.2, high=101.2, low=100.1, close=101.1),
    ]

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        levels,
        candles,
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-1",
    )

    assert result.setup_status == "triggered"
    assert result.trade_payload is not None
    assert result.trade_payload["quantity"] == "1.0"
    assert result.trade_payload["gross_pnl"] == result.trade_payload["net_pnl"]
    assert result.trade_payload["risk_amount"] == "0.52"
    assert result.trade_payload["exit_reason"] == "target_hit"
    assert result.trade_payload["trade_metadata_json"]["pnl_semantics"] == "normalized_one_share"
    assert result.trade_payload["trade_metadata_json"]["position_sizing_mode"] == "fixed_quantity_1"
    assert result.trade_payload["trade_metadata_json"]["fees_included"] is False
    assert result.trade_payload["trade_metadata_json"]["slippage_included"] is False
    assert result.trade_payload["trade_metadata_json"]["target_gap_fill"] is False


def test_trade_simulation_triggers_short_entry_and_hits_target() -> None:
    signal = _short_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("short"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=100.2, low=99.8, close=99.9),
            _custom_candle(22, open_price=99.8, high=99.9, low=98.9, close=99.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-short-1",
    )

    assert result.setup_status == "triggered"
    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "target_hit"
    assert result.trade_payload["r_multiple"] == "2.0"


def test_trade_simulation_expires_when_next_candle_does_not_trigger() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [signal.candle, _custom_candle(21, open_price=99.8, high=99.9, low=99.6, close=99.7)],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-2",
    )

    assert result.setup_status == "expired"
    assert result.rejection_reason == "entry_not_triggered"
    assert result.trade_payload is None


def test_trade_simulation_honors_entry_trigger_wait_bars() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig.from_parameters({"entry_trigger_wait_bars": 2})

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=99.8, high=99.9, low=99.6, close=99.7),
            _custom_candle(22, open_price=100.0, high=101.2, low=99.8, close=101.1),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-wait",
    )

    assert result.setup_status == "triggered"
    assert result.triggered_at == _time(22)
    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "target_hit"


def test_trade_simulation_expires_when_trigger_candle_is_at_entry_cutoff() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(369, open_price=99.6, high=100.0, low=99.5, close=99.9),
    )
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(370, open_price=100.0, high=100.2, low=99.8, close=100.1),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-cutoff",
    )

    assert result.setup_status == "expired"
    assert result.rejection_reason == "entry_after_cutoff"
    assert result.trade_payload is None


def test_trade_simulation_recalculates_target_after_gap_entry() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()
    levels = planned_trade_levels(signal, config=config)

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        levels,
        [
            signal.candle,
            _custom_candle(21, open_price=100.5, high=100.7, low=100.4, close=100.6),
            _custom_candle(22, open_price=100.6, high=102.6, low=100.5, close=102.5),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-3",
    )

    assert result.actual_entry_price == 100.5
    assert result.actual_target_price == 102.52
    assert result.trade_payload is not None
    metadata = result.trade_payload["trade_metadata_json"]
    assert metadata["entry_gap_fill"] is True
    assert metadata["planned_vs_actual_entry"] == {
        "planned": levels.entry_price,
        "actual": 100.5,
    }


def test_trade_simulation_recalculates_short_target_after_gap_entry() -> None:
    signal = _short_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()
    levels = planned_trade_levels(signal, config=config)

    result = simulate_entry_and_trade(
        _structure("short"),
        signal,
        levels,
        [
            signal.candle,
            _custom_candle(21, open_price=99.5, high=99.8, low=99.4, close=99.6),
            _custom_candle(22, open_price=99.4, high=99.5, low=97.4, close=97.5),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-short-gap",
    )

    assert result.actual_entry_price == 99.5
    assert result.actual_target_price == 97.48
    assert result.trade_payload is not None
    metadata = result.trade_payload["trade_metadata_json"]
    assert metadata["entry_gap_fill"] is True
    assert metadata["planned_vs_actual_entry"] == {
        "planned": levels.entry_price,
        "actual": 99.5,
    }


def test_trade_simulation_marks_entry_candle_stop_as_same_candle_stop() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [signal.candle, _custom_candle(21, open_price=100.0, high=100.2, low=99.4, close=99.5)],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-4",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "same_candle_stop"


def test_trade_simulation_marks_short_entry_candle_stop_as_same_candle_stop() -> None:
    signal = _short_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("short"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=100.6, low=99.8, close=100.4),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-short-stop",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "same_candle_stop"


def test_trade_simulation_entry_candle_target_without_stop_hits_target() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=101.1, low=99.8, close=101.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-same-candle-target",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "target_hit"


def test_trade_simulation_entry_candle_stop_and_target_uses_same_candle_stop() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=101.1, low=99.4, close=100.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-same-candle-stop-target",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "same_candle_stop"
    metadata = result.trade_payload["trade_metadata_json"]
    assert metadata["same_candle_stop_target"] is True


def test_trade_simulation_stop_wins_when_stop_and_target_hit_same_later_candle() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=100.2, low=99.8, close=100.1),
            _custom_candle(22, open_price=100.1, high=101.2, low=99.4, close=100.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-5",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "stop_hit"
    metadata = result.trade_payload["trade_metadata_json"]
    assert metadata["same_candle_stop_target"] is True


def test_trade_simulation_adverse_anchor_break_invalidates_before_entry() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long", anchor=_anchor("long", anchor_low=99.0, anchor_high=101.1)),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=99.6, high=99.9, low=98.9, close=99.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-anchor-adverse",
    )

    assert result.setup_status == "invalidated"
    assert result.rejection_reason == "anchor_low_broken_before_entry"
    assert result.trade_payload is None


def test_trade_simulation_profit_side_anchor_break_does_not_block_valid_entry() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long", anchor=_anchor("long", anchor_low=99.0, anchor_high=101.1)),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=101.2, low=99.8, close=101.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-anchor-profit",
    )

    assert result.setup_status == "triggered"
    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "target_hit"


def test_trade_simulation_short_adverse_anchor_break_invalidates_before_entry() -> None:
    signal = _short_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("short", anchor=_anchor("short", anchor_low=98.9, anchor_high=101.1)),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.4, high=101.2, low=100.2, close=100.8),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-short-anchor-adverse",
    )

    assert result.setup_status == "invalidated"
    assert result.rejection_reason == "anchor_high_broken_before_entry"
    assert result.trade_payload is None


def test_trade_simulation_short_profit_side_anchor_break_does_not_block_valid_entry() -> None:
    signal = _short_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("short", anchor=_anchor("short", anchor_low=98.9, anchor_high=101.1)),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=100.2, low=98.8, close=99.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-short-anchor-profit",
    )

    assert result.setup_status == "triggered"
    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "target_hit"


def test_trade_simulation_force_closes_at_259_ct() -> None:
    signal = qualify_signal_bar(
        "long",
        _custom_candle(360, open_price=99.6, high=100.0, low=99.5, close=99.9),
    )
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(361, open_price=100.0, high=100.2, low=99.8, close=100.1),
            _custom_candle(389, open_price=100.1, high=100.2, low=99.9, close=100.0),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-6",
    )

    assert result.trade_payload is not None
    assert result.trade_payload["exit_reason"] == "session_force_close"
    assert result.trade_payload["exit_price"] == "100.0"


def test_trade_simulation_marks_missing_force_close_candle_invalidated() -> None:
    signal = _long_signal()
    assert signal is not None
    config = TwoLeggedPullbackConfig()

    result = simulate_entry_and_trade(
        _structure("long"),
        signal,
        planned_trade_levels(signal, config=config),
        [
            signal.candle,
            _custom_candle(21, open_price=100.0, high=100.2, low=99.8, close=100.1),
        ],
        config=config,
        symbol="SPY",
        setup_key="SPY-setup-end-of-data",
    )

    assert result.setup_status == "invalidated"
    assert result.rejection_reason == "missing_force_close_candle"
    assert result.trade_payload is None


def _candles_from_highs_and_lows(highs: list[float], lows: list[float]) -> list[BacktestCandle]:
    return [
        _candle(index, high=high, low=low)
        for index, (high, low) in enumerate(zip(highs, lows, strict=False))
    ]


def _candle(
    offset_minutes: int,
    *,
    high: float,
    low: float,
    symbol: str = "SPY",
    timeframe: str = "1m",
) -> BacktestCandle:
    return _candle_at(
        _time(offset_minutes),
        high=high,
        low=low,
        symbol=symbol,
        timeframe=timeframe,
    )


def _candle_at(
    ts_event: datetime,
    *,
    high: float,
    low: float,
    symbol: str = "SPY",
    timeframe: str = "1m",
) -> BacktestCandle:
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


def _custom_candle(
    offset_minutes: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> BacktestCandle:
    return BacktestCandle(
        symbol="SPY",
        ts_event=_time(offset_minutes),
        session_date=date(2024, 1, 2),
        timeframe="1m",
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def _long_signal():
    return qualify_signal_bar(
        "long",
        _custom_candle(20, open_price=99.6, high=100.0, low=99.5, close=99.9),
    )


def _short_signal():
    return qualify_signal_bar(
        "short",
        _custom_candle(20, open_price=100.4, high=100.5, low=100.0, close=100.1),
    )


def _empty_context() -> TwoLeggedPullbackContext:
    return TwoLeggedPullbackContext(
        ema_by_time={},
        vwap_by_time={},
        previous_day_levels=None,
        premarket_levels=None,
        skipped_symbol_days=[],
    )


def _time(offset_minutes: int) -> datetime:
    return datetime(2024, 1, 2, 14, 30, tzinfo=UTC) + timedelta(minutes=offset_minutes)


def _anchor(side: TestSetupSide, *, anchor_low: float, anchor_high: float) -> AnchorRange:
    return AnchorRange(
        side=side,
        anchor_high=anchor_high,
        anchor_high_time=_time(0),
        anchor_low=anchor_low,
        anchor_low_time=_time(0),
    )


def _leg(
    direction: RawLegDirection,
    status: RawLegStatus,
    start_minute: int,
    *,
    high: float,
    low: float,
) -> RawLeg:
    return RawLeg(
        leg_direction=direction,
        status=status,
        start_bar_time=_time(start_minute),
        start_price=high if direction == "up" else low,
        end_bar_time=_time(start_minute),
        bar_count=1,
        leg_high_price=high,
        leg_high_bar_time=_time(start_minute),
        leg_low_price=low,
        leg_low_bar_time=_time(start_minute),
        switch_bar_time=_time(start_minute + 1) if status == "confirmed" else None,
    )


def _structure(
    side: TestSetupSide,
    *,
    anchor: AnchorRange | None = None,
    leg2: RawLeg | None = None,
):
    if side == "long":
        leg1 = _leg("down", "confirmed", 1, high=101.0, low=100.0)
        middle = _leg("up", "confirmed", 2, high=100.8, low=100.1)
        default_leg2 = _leg("down", "active", 3, high=100.5, low=99.9)
    else:
        leg1 = _leg("up", "confirmed", 1, high=101.0, low=100.0)
        middle = _leg("down", "confirmed", 2, high=100.8, low=100.1)
        default_leg2 = _leg("up", "active", 3, high=101.1, low=100.3)

    structures = detect_two_legged_pullback_structures(
        [leg1, middle, leg2 or default_leg2],
        [anchor] if anchor is not None else [],
        use_anchor_context=anchor is not None,
    )
    return structures[0]
