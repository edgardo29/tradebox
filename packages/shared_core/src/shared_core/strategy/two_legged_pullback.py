"""SPY intraday two-legged pullback strategy logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from typing import Any, Literal
from zoneinfo import ZoneInfo

from shared_core.backtesting.candles import (
    BacktestCandle,
    BacktestCandleValidationError,
    validate_backtest_candles,
)
from shared_core.backtesting.config import BacktestConfig
from shared_core.backtesting.strategy import BacktestStrategyResult
from shared_core.strategy.raw_legs import RawLeg, detect_raw_legs

SetupSide = Literal["long", "short"]
StructuralSwingKind = Literal["high", "low"]
SignalBarType = Literal["momentum", "rejection"]
SetupStatus = Literal["pending_entry", "triggered", "expired", "filtered_out", "invalidated"]
CENTRAL_TIME = ZoneInfo("America/Chicago")
TRADING_START_CT = time(8, 30)
ENTRY_CUTOFF_CT = time(14, 40)
FORCE_CLOSE_CT = time(14, 59)
DEFAULT_PREMARKET_START_CT = time(7, 0)
ANALYSIS_END_CT = FORCE_CLOSE_CT


@dataclass(frozen=True)
class TwoLeggedPullbackConfig:
    """Configurable V1 two-legged pullback parameters."""

    swing_left_bars: int = 3
    swing_right_bars: int = 3
    entry_trigger_wait_bars: int = 1
    entry_break_buffer: float = 0.01
    stop_break_buffer: float = 0.01
    target_r_multiple: float = 2.0
    use_anchor_context: bool = True
    use_ema_context: bool = True
    use_vwap_context: bool = False
    use_previous_day_level_filter: bool = False
    use_premarket_level_filter: bool = False
    ema_length: int = 20
    ema_near_max_distance: float = 0.15
    vwap_near_max_distance: float = 0.15
    level_near_max_distance: float = 0.15
    use_min_anchor_range_filter: bool = True
    min_anchor_range: float = 0.30
    use_raw_leg_chop_filter: bool = True
    chop_lookback_bars: int = 12
    max_raw_leg_switches: int = 5
    use_min_signal_bar_range_filter: bool = True
    min_signal_bar_range: float = 0.05
    use_single_open_trade_filter: bool = True
    premarket_warmup_start: time = DEFAULT_PREMARKET_START_CT
    previous_day_levels: dict[str, float] | None = None

    def __post_init__(self) -> None:
        """Validate strategy parameters that affect rule execution."""

        _require_positive_int("swing_left_bars", self.swing_left_bars)
        _require_positive_int("swing_right_bars", self.swing_right_bars)
        _require_positive_int("entry_trigger_wait_bars", self.entry_trigger_wait_bars)
        _require_positive_int("ema_length", self.ema_length)
        _require_non_negative_int("chop_lookback_bars", self.chop_lookback_bars)
        _require_non_negative_int("max_raw_leg_switches", self.max_raw_leg_switches)
        _require_non_negative_float("entry_break_buffer", self.entry_break_buffer)
        _require_non_negative_float("stop_break_buffer", self.stop_break_buffer)
        _require_positive_float("target_r_multiple", self.target_r_multiple)
        _require_non_negative_float("ema_near_max_distance", self.ema_near_max_distance)
        _require_non_negative_float("vwap_near_max_distance", self.vwap_near_max_distance)
        _require_non_negative_float("level_near_max_distance", self.level_near_max_distance)
        _require_non_negative_float("min_anchor_range", self.min_anchor_range)
        _require_non_negative_float("min_signal_bar_range", self.min_signal_bar_range)

    @classmethod
    def from_parameters(cls, parameters: dict[str, Any] | None) -> TwoLeggedPullbackConfig:
        """Build strategy config from a backtest parameter mapping."""

        values = dict(parameters or {})
        return cls(
            swing_left_bars=_int_parameter(values, "swing_left_bars", cls.swing_left_bars),
            swing_right_bars=_int_parameter(values, "swing_right_bars", cls.swing_right_bars),
            entry_trigger_wait_bars=_int_parameter(
                values,
                "entry_trigger_wait_bars",
                cls.entry_trigger_wait_bars,
            ),
            entry_break_buffer=_float_parameter(
                values,
                "entry_break_buffer",
                cls.entry_break_buffer,
            ),
            stop_break_buffer=_float_parameter(values, "stop_break_buffer", cls.stop_break_buffer),
            target_r_multiple=_float_parameter(
                values,
                "target_r_multiple",
                cls.target_r_multiple,
            ),
            use_anchor_context=_bool_parameter(
                values,
                "use_anchor_context",
                cls.use_anchor_context,
            ),
            use_ema_context=_bool_parameter(values, "use_ema_context", cls.use_ema_context),
            use_vwap_context=_bool_parameter(values, "use_vwap_context", cls.use_vwap_context),
            use_previous_day_level_filter=_bool_parameter(
                values,
                "use_previous_day_level_filter",
                cls.use_previous_day_level_filter,
            ),
            use_premarket_level_filter=_bool_parameter(
                values,
                "use_premarket_level_filter",
                cls.use_premarket_level_filter,
            ),
            ema_length=_int_parameter(values, "ema_length", cls.ema_length),
            ema_near_max_distance=_float_parameter(
                values,
                "ema_near_max_distance",
                cls.ema_near_max_distance,
            ),
            vwap_near_max_distance=_float_parameter(
                values,
                "vwap_near_max_distance",
                cls.vwap_near_max_distance,
            ),
            level_near_max_distance=_float_parameter(
                values,
                "level_near_max_distance",
                cls.level_near_max_distance,
            ),
            use_min_anchor_range_filter=_bool_parameter(
                values,
                "use_min_anchor_range_filter",
                cls.use_min_anchor_range_filter,
            ),
            min_anchor_range=_float_parameter(values, "min_anchor_range", cls.min_anchor_range),
            use_raw_leg_chop_filter=_bool_parameter(
                values,
                "use_raw_leg_chop_filter",
                cls.use_raw_leg_chop_filter,
            ),
            chop_lookback_bars=_int_parameter(
                values,
                "chop_lookback_bars",
                cls.chop_lookback_bars,
            ),
            max_raw_leg_switches=_int_parameter(
                values,
                "max_raw_leg_switches",
                cls.max_raw_leg_switches,
            ),
            use_min_signal_bar_range_filter=_bool_parameter(
                values,
                "use_min_signal_bar_range_filter",
                cls.use_min_signal_bar_range_filter,
            ),
            min_signal_bar_range=_float_parameter(
                values,
                "min_signal_bar_range",
                cls.min_signal_bar_range,
            ),
            use_single_open_trade_filter=_bool_parameter(
                values,
                "use_single_open_trade_filter",
                cls.use_single_open_trade_filter,
            ),
            previous_day_levels=_previous_day_levels(values.get("previous_day_levels")),
        )


@dataclass(frozen=True)
class PremarketLevels:
    """Premarket high/low levels for a CT trade date."""

    high: float
    low: float


@dataclass(frozen=True)
class TwoLeggedPullbackContext:
    """Calculated context values used by the strategy."""

    ema_by_time: dict[datetime, float]
    vwap_by_time: dict[datetime, float]
    previous_day_levels: dict[str, float] | None
    premarket_levels: PremarketLevels | None
    skipped_symbol_days: list[dict[str, object]]

    @property
    def should_skip_symbol_day(self) -> bool:
        """Return true when required context is missing before setup detection."""

        return bool(self.skipped_symbol_days)


@dataclass(frozen=True)
class StructuralSwing:
    """A confirmed structural swing high or low."""

    kind: StructuralSwingKind
    price: float
    pivot_bar_time: datetime
    confirmed_at: datetime
    pivot_index: int


@dataclass(frozen=True)
class AnchorRange:
    """Anchor range used to frame a two-legged pullback."""

    side: SetupSide
    anchor_high: float
    anchor_high_time: datetime
    anchor_low: float
    anchor_low_time: datetime

    @property
    def anchor_range(self) -> float:
        """Return the absolute high/low anchor range."""

        return self.anchor_high - self.anchor_low


@dataclass(frozen=True)
class TwoLeggedPullbackStructure:
    """A raw-leg two-legged pullback structure inside an optional anchor range."""

    side: SetupSide
    anchor: AnchorRange | None
    leg1: RawLeg
    middle_move: RawLeg
    leg2: RawLeg


@dataclass(frozen=True)
class SignalBar:
    """A validated signal bar after leg 2."""

    side: SetupSide
    signal_type: SignalBarType
    candle: BacktestCandle
    candle_range: float
    body: float
    upper_wick: float
    lower_wick: float


@dataclass(frozen=True)
class PlannedTradeLevels:
    """Planned entry, stop, target, and risk from the signal bar."""

    entry_price: float
    stop_price: float
    target_price: float
    risk_per_share: float


@dataclass(frozen=True)
class SetupFilterResult:
    """Pass/fail details for V1 setup filters."""

    passed: bool
    rejection_reason: str | None
    details: dict[str, object]


@dataclass(frozen=True)
class TradeSimulationResult:
    """Entry/exit simulation result for a detected setup."""

    setup_status: SetupStatus
    rejection_reason: str | None
    triggered_at: datetime | None
    actual_entry_price: float | None
    actual_stop_price: float | None
    actual_target_price: float | None
    trade_payload: dict[str, object] | None


@dataclass(frozen=True)
class TwoLeggedPullbackStrategy:
    """V1 SPY intraday two-legged pullback strategy."""

    name: str = "two_legged_pullback"
    version: str = "0.1.0"

    def run(
        self,
        *,
        config: BacktestConfig,
        candles: list[BacktestCandle],
    ) -> BacktestStrategyResult:
        """Run V1 setup detection and trade simulation from provided candles."""

        validate_backtest_candles(
            candles,
            expected_symbol=config.symbol,
            expected_timeframe=config.timeframe,
        )
        strategy_config = TwoLeggedPullbackConfig.from_parameters(config.parameters)
        context = build_two_legged_pullback_context(
            candles,
            config=strategy_config,
            symbol=config.symbol,
            instrument_id=_optional_metadata_str(config.metadata, "instrument_id"),
        )
        if context.should_skip_symbol_day:
            return BacktestStrategyResult(
                metrics={
                    "skipped_symbol_days": context.skipped_symbol_days,
                    "skip_reason": "missing_required_context",
                }
            )

        analysis_candles = _analysis_window_candles(candles, config=strategy_config)
        missing_context = _missing_analysis_window_context(
            analysis_candles,
            config=strategy_config,
        )
        if missing_context:
            return BacktestStrategyResult(
                metrics={
                    "skipped_symbol_days": [
                        _skipped_symbol_day(
                            analysis_candles or candles,
                            symbol=config.symbol,
                            instrument_id=_optional_metadata_str(
                                config.metadata,
                                "instrument_id",
                            ),
                            reason="invalid_candle_data",
                            missing_context=missing_context,
                        )
                    ],
                    "skip_reason": "invalid_candle_data",
                }
            )

        context = build_two_legged_pullback_context(
            analysis_candles,
            config=strategy_config,
            symbol=config.symbol,
            instrument_id=_optional_metadata_str(config.metadata, "instrument_id"),
        )

        try:
            raw_legs = detect_raw_legs(analysis_candles, expected_symbol=config.symbol)
        except BacktestCandleValidationError as exc:
            return BacktestStrategyResult(
                metrics={
                    "skipped_symbol_days": [
                        _skipped_symbol_day(
                            analysis_candles,
                            symbol=config.symbol,
                            instrument_id=_optional_metadata_str(
                                config.metadata,
                                "instrument_id",
                            ),
                            reason="invalid_candle_data",
                            missing_context=[],
                        )
                    ],
                    "skip_error": str(exc),
                }
            )

        swings = detect_structural_swings(
            analysis_candles,
            left_bars=strategy_config.swing_left_bars,
            right_bars=strategy_config.swing_right_bars,
        )
        anchors = build_anchor_ranges(swings)
        structures = detect_two_legged_pullback_structures(
            raw_legs,
            anchors,
            use_anchor_context=strategy_config.use_anchor_context,
        )

        detected_setups: list[dict[str, object]] = []
        simulated_trades: list[dict[str, object]] = []
        open_trade_until: datetime | None = None
        for structure in structures:
            signal_bar = find_signal_bar_for_structure(
                structure,
                analysis_candles,
                config=strategy_config,
            )
            if signal_bar is None or not _signal_bar_time_allowed(signal_bar):
                continue

            levels = planned_trade_levels(signal_bar, config=strategy_config)
            filter_result = evaluate_setup_filters(
                structure,
                signal_bar,
                context,
                raw_legs,
                config=strategy_config,
            )
            setup_key = _setup_key(config.symbol, signal_bar)
            if filter_result.passed and _single_open_trade_blocked(
                signal_bar,
                open_trade_until=open_trade_until,
                config=strategy_config,
            ):
                filter_result = _with_single_open_trade_failure(filter_result)

            if not filter_result.passed:
                detected_setups.append(
                    build_detected_setup_payload(
                        structure,
                        signal_bar,
                        levels,
                        filter_result,
                        config=strategy_config,
                        context=context,
                        setup_status="filtered_out",
                        symbol=config.symbol,
                    )
                )
                continue

            simulation = simulate_entry_and_trade(
                structure,
                signal_bar,
                levels,
                analysis_candles,
                config=strategy_config,
                symbol=config.symbol,
                setup_key=setup_key,
            )
            detected_setups.append(
                build_detected_setup_payload(
                    structure,
                    signal_bar,
                    levels,
                    filter_result,
                    config=strategy_config,
                    context=context,
                    setup_status=simulation.setup_status,
                    symbol=config.symbol,
                    rejection_reason=simulation.rejection_reason,
                    triggered_at=simulation.triggered_at,
                )
            )
            if simulation.trade_payload is not None:
                simulated_trades.append(simulation.trade_payload)
                exit_at = simulation.trade_payload.get("exit_at")
                if isinstance(exit_at, datetime):
                    open_trade_until = exit_at

        return BacktestStrategyResult(
            detected_setups=detected_setups,
            simulated_trades=simulated_trades,
            metrics={
                "raw_leg_count": len(raw_legs),
                "structural_swing_count": len(swings),
                "anchor_range_count": len(anchors),
                "two_legged_structure_count": len(structures),
                "skipped_symbol_days": context.skipped_symbol_days,
            },
        )


@dataclass(frozen=True)
class _ExitResult:
    exit_candle: BacktestCandle
    exit_price: float
    exit_reason: str
    stop_gap_fill: bool = False
    target_gap_fill: bool = False
    same_candle_stop_target: bool = False


def detect_structural_swings(
    candles: list[BacktestCandle],
    *,
    expected_symbol: str | None = None,
    left_bars: int = 3,
    right_bars: int = 3,
) -> list[StructuralSwing]:
    """Detect strict structural swing highs and lows without lookahead bias."""

    if left_bars < 1 or right_bars < 1:
        raise ValueError("Structural swing left_bars and right_bars must be positive.")
    if not candles:
        return []

    validate_backtest_candles(
        candles,
        expected_symbol=expected_symbol,
        expected_timeframe="1m",
    )

    swings: list[StructuralSwing] = []
    for pivot_index in range(left_bars, len(candles) - right_bars):
        pivot = candles[pivot_index]
        left_side = candles[pivot_index - left_bars : pivot_index]
        right_side = candles[pivot_index + 1 : pivot_index + right_bars + 1]
        confirmed_at = candles[pivot_index + right_bars].ts_event

        if all(pivot.high > candle.high for candle in [*left_side, *right_side]):
            swings.append(
                StructuralSwing(
                    kind="high",
                    price=pivot.high,
                    pivot_bar_time=pivot.ts_event,
                    confirmed_at=confirmed_at,
                    pivot_index=pivot_index,
                )
            )
        if all(pivot.low < candle.low for candle in [*left_side, *right_side]):
            swings.append(
                StructuralSwing(
                    kind="low",
                    price=pivot.low,
                    pivot_bar_time=pivot.ts_event,
                    confirmed_at=confirmed_at,
                    pivot_index=pivot_index,
                )
            )

    return swings


def build_anchor_ranges(swings: list[StructuralSwing]) -> list[AnchorRange]:
    """Build long and short anchor ranges from confirmed structural swings."""

    anchors: list[AnchorRange] = []
    latest_high: StructuralSwing | None = None
    latest_low: StructuralSwing | None = None

    for swing in sorted(swings, key=lambda item: (item.pivot_index, item.kind)):
        if swing.kind == "high":
            if latest_low is not None and swing.price > latest_low.price:
                anchors.append(
                    AnchorRange(
                        side="long",
                        anchor_high=swing.price,
                        anchor_high_time=swing.pivot_bar_time,
                        anchor_low=latest_low.price,
                        anchor_low_time=latest_low.pivot_bar_time,
                    )
                )
            latest_high = swing
        else:
            if latest_high is not None and latest_high.price > swing.price:
                anchors.append(
                    AnchorRange(
                        side="short",
                        anchor_high=latest_high.price,
                        anchor_high_time=latest_high.pivot_bar_time,
                        anchor_low=swing.price,
                        anchor_low_time=swing.pivot_bar_time,
                    )
                )
            latest_low = swing

    return anchors


def build_two_legged_pullback_context(
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
    symbol: str,
    instrument_id: str | None = None,
) -> TwoLeggedPullbackContext:
    """Calculate context values and required-context skip metadata."""

    analysis_candles = _analysis_window_candles(candles, config=config)
    previous_day_levels = config.previous_day_levels
    skipped_symbol_days: list[dict[str, object]] = []
    if config.use_previous_day_level_filter and previous_day_levels is None and candles:
        skipped_symbol_days.append(
            {
                "instrument_id": instrument_id,
                "symbol": symbol.upper(),
                "trade_date": _ct_trade_date((analysis_candles or candles)[0]).isoformat(),
                "reason": "missing_required_context",
                "missing_context": ["previous_day_levels"],
            }
        )

    return TwoLeggedPullbackContext(
        ema_by_time=_ema_by_time(analysis_candles, length=config.ema_length),
        vwap_by_time=_vwap_by_time(analysis_candles),
        previous_day_levels=previous_day_levels,
        premarket_levels=_premarket_levels(analysis_candles, config=config),
        skipped_symbol_days=skipped_symbol_days,
    )


def detect_two_legged_pullback_structures(
    raw_legs: list[RawLeg],
    anchors: list[AnchorRange],
    *,
    use_anchor_context: bool = True,
) -> list[TwoLeggedPullbackStructure]:
    """Detect raw-leg two-legged pullback structures."""

    structures: list[TwoLeggedPullbackStructure] = []

    for index in range(0, len(raw_legs) - 2):
        leg1 = raw_legs[index]
        middle_move = raw_legs[index + 1]
        leg2 = raw_legs[index + 2]

        if leg1.status != "confirmed" or middle_move.status != "confirmed":
            continue

        side = _structure_side(leg1, middle_move, leg2)
        if side is None:
            continue

        anchor = _latest_anchor_for_structure(anchors, side=side, leg1=leg1)
        if use_anchor_context:
            if anchor is None:
                continue
            if not _legs_stay_inside_anchor(anchor, [leg1, middle_move, leg2]):
                continue

        structures.append(
            TwoLeggedPullbackStructure(
                side=side,
                anchor=anchor,
                leg1=leg1,
                middle_move=middle_move,
                leg2=leg2,
            )
        )

    return structures


def find_signal_bar_for_structure(
    structure: TwoLeggedPullbackStructure,
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
) -> SignalBar | None:
    """Find the first valid signal bar for a two-legged structure."""

    candidate_index = _signal_candidate_start_index(structure, candles)
    if candidate_index is None:
        return None

    for candle in candles[candidate_index:]:
        ct_time = _ct_time(candle)
        if ct_time >= ENTRY_CUTOFF_CT:
            return None
        if ct_time < TRADING_START_CT:
            continue
        if (
            config.use_anchor_context
            and structure.anchor is not None
            and _candle_breaks_anchor(candle, structure.anchor)
        ):
            return None

        signal_bar = qualify_signal_bar(
            structure.side,
            candle,
            anchor=structure.anchor,
            use_anchor_context=config.use_anchor_context,
        )
        if signal_bar is not None:
            return signal_bar

    return None


def qualify_signal_bar(
    side: SetupSide,
    candle: BacktestCandle,
    *,
    anchor: AnchorRange | None = None,
    use_anchor_context: bool = True,
) -> SignalBar | None:
    """Validate a candle as a long or short signal bar."""

    if use_anchor_context and anchor is not None:
        if candle.low < anchor.anchor_low or candle.high > anchor.anchor_high:
            return None

    candle_range = candle.high - candle.low
    if candle_range <= 0:
        return None

    body = abs(candle.close - candle.open)
    upper_wick = candle.high - max(candle.open, candle.close)
    lower_wick = min(candle.open, candle.close) - candle.low

    if side == "long":
        if candle.close <= candle.open:
            return None
        if candle.close < candle.low + (candle_range * 2 / 3):
            return None
        signal_type = _bullish_signal_type(
            candle_range=candle_range,
            body=body,
            upper_wick=upper_wick,
            lower_wick=lower_wick,
        )
    else:
        if candle.close >= candle.open:
            return None
        if candle.close > candle.low + (candle_range / 3):
            return None
        signal_type = _bearish_signal_type(
            candle_range=candle_range,
            body=body,
            upper_wick=upper_wick,
            lower_wick=lower_wick,
        )

    if signal_type is None:
        return None

    return SignalBar(
        side=side,
        signal_type=signal_type,
        candle=candle,
        candle_range=candle_range,
        body=body,
        upper_wick=upper_wick,
        lower_wick=lower_wick,
    )


def planned_trade_levels(
    signal_bar: SignalBar,
    *,
    config: TwoLeggedPullbackConfig,
) -> PlannedTradeLevels:
    """Calculate planned entry, stop, target, and risk from a signal bar."""

    if signal_bar.side == "long":
        entry_price = signal_bar.candle.high + config.entry_break_buffer
        stop_price = signal_bar.candle.low - config.stop_break_buffer
        risk_per_share = entry_price - stop_price
        target_price = entry_price + (config.target_r_multiple * risk_per_share)
    else:
        entry_price = signal_bar.candle.low - config.entry_break_buffer
        stop_price = signal_bar.candle.high + config.stop_break_buffer
        risk_per_share = stop_price - entry_price
        target_price = entry_price - (config.target_r_multiple * risk_per_share)

    return PlannedTradeLevels(
        entry_price=round(entry_price, 6),
        stop_price=round(stop_price, 6),
        target_price=round(target_price, 6),
        risk_per_share=round(risk_per_share, 6),
    )


def evaluate_setup_filters(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    context: TwoLeggedPullbackContext,
    raw_legs: list[RawLeg],
    *,
    config: TwoLeggedPullbackConfig,
) -> SetupFilterResult:
    """Evaluate V1 filters after valid structure and signal-bar detection."""

    details: dict[str, object] = {}
    rejection_reason: str | None = None

    if (
        config.use_anchor_context
        and config.use_min_anchor_range_filter
        and structure.anchor is not None
    ):
        anchor_range_passed = structure.anchor.anchor_range >= config.min_anchor_range
        details["anchor_range"] = {
            "passed": anchor_range_passed,
            "value": structure.anchor.anchor_range,
            "minimum": config.min_anchor_range,
        }
        rejection_reason = rejection_reason or (
            None if anchor_range_passed else "anchor_range_too_small"
        )

    if config.use_min_signal_bar_range_filter:
        signal_range_passed = signal_bar.candle_range >= config.min_signal_bar_range
        details["signal_bar_range"] = {
            "passed": signal_range_passed,
            "value": signal_bar.candle_range,
            "minimum": config.min_signal_bar_range,
        }
        rejection_reason = rejection_reason or (
            None if signal_range_passed else "signal_bar_too_small"
        )

    ema_details = _evaluate_ema_context(structure, signal_bar, context, config=config)
    details["ema_context"] = ema_details
    if config.use_ema_context:
        rejection_reason = rejection_reason or (
            None if bool(ema_details["passed"]) else "ema_context_failed"
        )

    vwap_details = _evaluate_vwap_context(structure, signal_bar, context, config=config)
    details["vwap_context"] = vwap_details
    if config.use_vwap_context:
        rejection_reason = rejection_reason or (
            None if bool(vwap_details["passed"]) else "vwap_context_failed"
        )

    previous_day_details = _evaluate_level_context(
        structure,
        signal_bar,
        levels=context.previous_day_levels,
        max_distance=config.level_near_max_distance,
    )
    details["previous_day_levels"] = previous_day_details
    if config.use_previous_day_level_filter:
        rejection_reason = rejection_reason or (
            None if bool(previous_day_details["passed"]) else "previous_day_level_context_failed"
        )

    premarket_details = _evaluate_premarket_context(
        structure,
        signal_bar,
        context,
        max_distance=config.level_near_max_distance,
    )
    details["premarket_levels"] = premarket_details
    if config.use_premarket_level_filter:
        rejection_reason = rejection_reason or (
            None if bool(premarket_details["passed"]) else "premarket_level_context_failed"
        )

    if config.use_raw_leg_chop_filter:
        switch_count = _raw_leg_switch_count_near_signal(raw_legs, signal_bar, config=config)
        chop_passed = switch_count <= config.max_raw_leg_switches
        details["raw_leg_chop"] = {
            "passed": chop_passed,
            "switch_count": switch_count,
            "maximum": config.max_raw_leg_switches,
            "lookback_bars": config.chop_lookback_bars,
        }
        rejection_reason = rejection_reason or (None if chop_passed else "raw_leg_chop")

    return SetupFilterResult(
        passed=rejection_reason is None,
        rejection_reason=rejection_reason,
        details=details,
    )


def build_detected_setup_payload(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    levels: PlannedTradeLevels,
    filter_result: SetupFilterResult,
    *,
    config: TwoLeggedPullbackConfig,
    context: TwoLeggedPullbackContext,
    setup_status: SetupStatus,
    symbol: str,
    rejection_reason: str | None = None,
    triggered_at: datetime | None = None,
) -> dict[str, object]:
    """Build the persistence payload for a detected setup."""

    signal_candle = signal_bar.candle
    setup_key = _setup_key(symbol, signal_bar)
    reason = rejection_reason or filter_result.rejection_reason
    return {
        "setup_key": setup_key,
        "setup_status": setup_status,
        "side": signal_bar.side,
        "timeframe": signal_candle.timeframe,
        "session_date": _ct_trade_date(signal_candle),
        "detected_at": signal_candle.ts_event,
        "setup_start_at": structure.leg1.start_bar_time,
        "setup_end_at": signal_candle.ts_event,
        "triggered_at": triggered_at,
        "entry_price": str(levels.entry_price),
        "stop_price": str(levels.stop_price),
        "target_price": str(levels.target_price),
        "rejection_reason": reason,
        "setup_metadata_json": {
            "symbol": symbol.upper(),
            "anchors": _anchor_metadata(structure.anchor),
            "legs": _legs_metadata(structure),
            "signal_bar": _signal_bar_metadata(signal_bar),
            "context": _context_metadata(context, signal_candle.ts_event),
            "filters": filter_result.details,
            "planned_trade": {
                "entry_price": levels.entry_price,
                "stop_price": levels.stop_price,
                "target_price": levels.target_price,
                "target_r_multiple": config.target_r_multiple,
                "risk_per_share": levels.risk_per_share,
                "entry_trigger_wait_bars": config.entry_trigger_wait_bars,
            },
        },
    }


def simulate_entry_and_trade(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    planned_levels: PlannedTradeLevels,
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
    symbol: str,
    setup_key: str,
) -> TradeSimulationResult:
    """Simulate entry trigger, stop/target exits, and session force close."""

    signal_index = _index_for_time(candles, signal_bar.candle.ts_event)
    if signal_index is None:
        return _pending_entry_result()

    for wait_offset in range(1, config.entry_trigger_wait_bars + 1):
        trigger_index = signal_index + wait_offset
        if trigger_index >= len(candles):
            return _pending_entry_result()

        trigger_candle = candles[trigger_index]
        if _ct_time(trigger_candle) >= ENTRY_CUTOFF_CT:
            return _expired_result("entry_after_cutoff")

        entry_triggered = _entry_triggered(signal_bar.side, trigger_candle, planned_levels)
        invalidation_reason = _pre_entry_anchor_break_reason(
            structure,
            trigger_candle,
            config=config,
            entry_triggered=entry_triggered,
        )
        if invalidation_reason is not None:
            return TradeSimulationResult(
                setup_status="invalidated",
                rejection_reason=invalidation_reason,
                triggered_at=None,
                actual_entry_price=None,
                actual_stop_price=None,
                actual_target_price=None,
                trade_payload=None,
            )

        if not entry_triggered:
            continue

        actual_entry = _entry_fill_price(signal_bar.side, trigger_candle, planned_levels)
        entry_gap_fill = actual_entry != planned_levels.entry_price
        actual_stop = planned_levels.stop_price
        actual_risk = _risk_per_share(signal_bar.side, actual_entry, actual_stop)
        actual_target = _target_price(signal_bar.side, actual_entry, actual_risk, config=config)
        exit_result = _simulate_exit(
            signal_bar.side,
            candles[trigger_index:],
            stop_price=actual_stop,
            target_price=actual_target,
        )
        if exit_result is None:
            return TradeSimulationResult(
                setup_status="invalidated",
                rejection_reason="missing_force_close_candle",
                triggered_at=None,
                actual_entry_price=None,
                actual_stop_price=None,
                actual_target_price=None,
                trade_payload=None,
            )
        return TradeSimulationResult(
            setup_status="triggered",
            rejection_reason=None,
            triggered_at=trigger_candle.ts_event,
            actual_entry_price=actual_entry,
            actual_stop_price=actual_stop,
            actual_target_price=actual_target,
            trade_payload=_trade_payload(
                signal_bar,
                setup_key=setup_key,
                symbol=symbol,
                entry_candle=trigger_candle,
                entry_price=actual_entry,
                stop_price=actual_stop,
                target_price=actual_target,
                risk_per_share=actual_risk,
                planned_entry_price=planned_levels.entry_price,
                entry_gap_fill=entry_gap_fill,
                exit_result=exit_result,
            ),
        )

    return _expired_result("entry_not_triggered")


def _structure_side(
    leg1: RawLeg,
    middle_move: RawLeg,
    leg2: RawLeg,
) -> SetupSide | None:
    directions = (leg1.leg_direction, middle_move.leg_direction, leg2.leg_direction)
    if directions == ("down", "up", "down"):
        return "long"
    if directions == ("up", "down", "up"):
        return "short"
    return None


def _latest_anchor_for_structure(
    anchors: list[AnchorRange],
    *,
    side: SetupSide,
    leg1: RawLeg,
) -> AnchorRange | None:
    matching = [
        anchor
        for anchor in anchors
        if anchor.side == side and _anchor_pullback_start_time(anchor) <= leg1.start_bar_time
    ]
    if not matching:
        return None
    return max(matching, key=_anchor_pullback_start_time)


def _anchor_pullback_start_time(anchor: AnchorRange) -> datetime:
    return anchor.anchor_high_time if anchor.side == "long" else anchor.anchor_low_time


def _legs_stay_inside_anchor(anchor: AnchorRange, legs: list[RawLeg]) -> bool:
    for leg in legs:
        if leg.leg_low_price < anchor.anchor_low:
            return False
        if leg.leg_high_price > anchor.anchor_high:
            return False
    return True


def _setup_key(symbol: str, signal_bar: SignalBar) -> str:
    return f"{symbol.upper()}-{signal_bar.candle.ts_event.isoformat()}-{signal_bar.side}"


def _optional_metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _skipped_symbol_day(
    candles: list[BacktestCandle],
    *,
    symbol: str,
    instrument_id: str | None,
    reason: str,
    missing_context: list[str],
) -> dict[str, object]:
    trade_date = _ct_trade_date(candles[0]).isoformat() if candles else None
    return {
        "instrument_id": instrument_id,
        "symbol": symbol.upper(),
        "trade_date": trade_date,
        "reason": reason,
        "missing_context": missing_context,
    }


def _analysis_window_candles(
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
) -> list[BacktestCandle]:
    return [
        candle
        for candle in candles
        if config.premarket_warmup_start <= _ct_time(candle) <= ANALYSIS_END_CT
    ]


def _missing_analysis_window_context(
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
) -> list[str]:
    if not candles:
        return ["analysis_window_candles"]

    trade_dates = {_ct_trade_date(candle) for candle in candles}
    if len(trade_dates) != 1:
        return ["single_ct_trade_date"]

    trade_date = next(iter(trade_dates))
    expected_start = _ct_datetime(trade_date, config.premarket_warmup_start)
    expected_end = _ct_datetime(trade_date, ANALYSIS_END_CT)
    if candles[0].ts_event != expected_start:
        return ["analysis_window_start"]
    if candles[-1].ts_event != expected_end:
        return ["analysis_window_end"]

    for previous, current in zip(candles, candles[1:], strict=False):
        if current.ts_event != previous.ts_event + timedelta(minutes=1):
            return ["continuous_1m_analysis_window"]

    return []


def _signal_bar_time_allowed(signal_bar: SignalBar) -> bool:
    ct_time = _ct_time(signal_bar.candle)
    return TRADING_START_CT <= ct_time < ENTRY_CUTOFF_CT


def _single_open_trade_blocked(
    signal_bar: SignalBar,
    *,
    open_trade_until: datetime | None,
    config: TwoLeggedPullbackConfig,
) -> bool:
    if not config.use_single_open_trade_filter or open_trade_until is None:
        return False
    return signal_bar.candle.ts_event < open_trade_until


def _with_single_open_trade_failure(filter_result: SetupFilterResult) -> SetupFilterResult:
    details = {
        **filter_result.details,
        "single_open_trade": {
            "passed": False,
        },
    }
    return SetupFilterResult(
        passed=False,
        rejection_reason="single_open_trade",
        details=details,
    )


def _pending_entry_result() -> TradeSimulationResult:
    return TradeSimulationResult(
        setup_status="pending_entry",
        rejection_reason=None,
        triggered_at=None,
        actual_entry_price=None,
        actual_stop_price=None,
        actual_target_price=None,
        trade_payload=None,
    )


def _expired_result(reason: str) -> TradeSimulationResult:
    return TradeSimulationResult(
        setup_status="expired",
        rejection_reason=reason,
        triggered_at=None,
        actual_entry_price=None,
        actual_stop_price=None,
        actual_target_price=None,
        trade_payload=None,
    )


def _index_for_time(candles: list[BacktestCandle], ts_event: datetime) -> int | None:
    for index, candle in enumerate(candles):
        if candle.ts_event == ts_event:
            return index
    return None


def _pre_entry_anchor_break_reason(
    structure: TwoLeggedPullbackStructure,
    candle: BacktestCandle,
    *,
    config: TwoLeggedPullbackConfig,
    entry_triggered: bool,
) -> str | None:
    if not config.use_anchor_context or structure.anchor is None:
        return None

    if structure.side == "long":
        if candle.low < structure.anchor.anchor_low:
            return "anchor_low_broken_before_entry"
        if not entry_triggered and candle.high > structure.anchor.anchor_high:
            return "anchor_high_broken_before_entry"
        return None

    if candle.high > structure.anchor.anchor_high:
        return "anchor_high_broken_before_entry"
    if not entry_triggered and candle.low < structure.anchor.anchor_low:
        return "anchor_low_broken_before_entry"
    return None


def _candle_breaks_anchor(candle: BacktestCandle, anchor: AnchorRange) -> bool:
    return candle.low < anchor.anchor_low or candle.high > anchor.anchor_high


def _entry_triggered(
    side: SetupSide,
    candle: BacktestCandle,
    planned_levels: PlannedTradeLevels,
) -> bool:
    if side == "long":
        return candle.high >= planned_levels.entry_price
    return candle.low <= planned_levels.entry_price


def _entry_fill_price(
    side: SetupSide,
    candle: BacktestCandle,
    planned_levels: PlannedTradeLevels,
) -> float:
    if side == "long" and candle.open > planned_levels.entry_price:
        return candle.open
    if side == "short" and candle.open < planned_levels.entry_price:
        return candle.open
    return planned_levels.entry_price


def _risk_per_share(side: SetupSide, entry_price: float, stop_price: float) -> float:
    risk = entry_price - stop_price if side == "long" else stop_price - entry_price
    return round(risk, 6)


def _target_price(
    side: SetupSide,
    entry_price: float,
    risk_per_share: float,
    *,
    config: TwoLeggedPullbackConfig,
) -> float:
    if side == "long":
        return round(entry_price + (config.target_r_multiple * risk_per_share), 6)
    return round(entry_price - (config.target_r_multiple * risk_per_share), 6)


def _simulate_exit(
    side: SetupSide,
    candles: list[BacktestCandle],
    *,
    stop_price: float,
    target_price: float,
) -> _ExitResult | None:
    for offset, candle in enumerate(candles):
        is_entry_candle = offset == 0
        stop_touched = _stop_touched(side, candle, stop_price)
        target_touched = _target_touched(side, candle, target_price)

        if is_entry_candle and stop_touched:
            return _ExitResult(
                exit_candle=candle,
                exit_price=_stop_fill_price(side, candle, stop_price),
                exit_reason="same_candle_stop",
                stop_gap_fill=_stop_gap_fill(side, candle, stop_price),
                same_candle_stop_target=target_touched,
            )

        if stop_touched and target_touched:
            return _ExitResult(
                exit_candle=candle,
                exit_price=_stop_fill_price(side, candle, stop_price),
                exit_reason="stop_hit",
                stop_gap_fill=_stop_gap_fill(side, candle, stop_price),
                same_candle_stop_target=True,
            )
        if stop_touched:
            return _ExitResult(
                exit_candle=candle,
                exit_price=_stop_fill_price(side, candle, stop_price),
                exit_reason="stop_hit",
                stop_gap_fill=_stop_gap_fill(side, candle, stop_price),
            )
        if target_touched:
            return _ExitResult(
                exit_candle=candle,
                exit_price=_target_fill_price(side, candle, target_price),
                exit_reason="target_hit",
                target_gap_fill=_target_gap_fill(side, candle, target_price),
            )
        if _ct_time(candle) >= FORCE_CLOSE_CT:
            return _ExitResult(
                exit_candle=candle,
                exit_price=candle.close,
                exit_reason="session_force_close",
            )

    return None


def _stop_touched(side: SetupSide, candle: BacktestCandle, stop_price: float) -> bool:
    return candle.low <= stop_price if side == "long" else candle.high >= stop_price


def _target_touched(side: SetupSide, candle: BacktestCandle, target_price: float) -> bool:
    return candle.high >= target_price if side == "long" else candle.low <= target_price


def _stop_gap_fill(side: SetupSide, candle: BacktestCandle, stop_price: float) -> bool:
    return candle.open < stop_price if side == "long" else candle.open > stop_price


def _target_gap_fill(side: SetupSide, candle: BacktestCandle, target_price: float) -> bool:
    return candle.open > target_price if side == "long" else candle.open < target_price


def _stop_fill_price(side: SetupSide, candle: BacktestCandle, stop_price: float) -> float:
    if _stop_gap_fill(side, candle, stop_price):
        return candle.open
    return stop_price


def _target_fill_price(side: SetupSide, candle: BacktestCandle, target_price: float) -> float:
    if _target_gap_fill(side, candle, target_price):
        return candle.open
    return target_price


def _trade_payload(
    signal_bar: SignalBar,
    *,
    setup_key: str,
    symbol: str,
    entry_candle: BacktestCandle,
    entry_price: float,
    stop_price: float,
    target_price: float,
    risk_per_share: float,
    planned_entry_price: float,
    entry_gap_fill: bool,
    exit_result: _ExitResult,
) -> dict[str, object]:
    quantity = 1.0
    gross_pnl_per_share = _gross_pnl_per_share(
        signal_bar.side,
        entry_price=entry_price,
        exit_price=exit_result.exit_price,
    )
    gross_pnl = gross_pnl_per_share * quantity
    risk_amount = risk_per_share * quantity
    return {
        "trade_key": f"{setup_key}-trade",
        "detected_setup_key": setup_key,
        "trade_status": "closed",
        "side": signal_bar.side,
        "entry_at": entry_candle.ts_event,
        "entry_price": str(round(entry_price, 6)),
        "exit_at": exit_result.exit_candle.ts_event,
        "exit_price": str(round(exit_result.exit_price, 6)),
        "stop_price": str(round(stop_price, 6)),
        "target_price": str(round(target_price, 6)),
        "quantity": str(round(quantity, 6)),
        "gross_pnl": str(round(gross_pnl, 6)),
        "net_pnl": str(round(gross_pnl, 6)),
        "risk_amount": str(round(risk_amount, 6)),
        "r_multiple": str(round(gross_pnl_per_share / risk_per_share, 6)),
        "exit_reason": exit_result.exit_reason,
        "trade_metadata_json": {
            "symbol": symbol.upper(),
            "entry_reason": "signal_bar_break",
            "pnl_semantics": "normalized_one_share",
            "position_sizing_mode": "fixed_quantity_1",
            "fees_included": False,
            "slippage_included": False,
            "entry_gap_fill": entry_gap_fill,
            "stop_gap_fill": exit_result.stop_gap_fill,
            "target_gap_fill": exit_result.target_gap_fill,
            "same_candle_stop_target": exit_result.same_candle_stop_target,
            "planned_vs_actual_entry": {
                "planned": round(planned_entry_price, 6),
                "actual": round(entry_price, 6),
            },
            "actual_risk_from_gap_fill": round(risk_per_share, 6),
        },
    }


def _gross_pnl_per_share(side: SetupSide, *, entry_price: float, exit_price: float) -> float:
    if side == "long":
        return exit_price - entry_price
    return entry_price - exit_price


def _signal_candidate_start_index(
    structure: TwoLeggedPullbackStructure,
    candles: list[BacktestCandle],
) -> int | None:
    time_to_index = {candle.ts_event: index for index, candle in enumerate(candles)}
    if structure.leg2.switch_bar_time is not None:
        return time_to_index.get(structure.leg2.switch_bar_time)

    leg2_start_index = time_to_index.get(structure.leg2.start_bar_time)
    if leg2_start_index is None:
        return None
    candidate_index = leg2_start_index + 1
    return candidate_index if candidate_index < len(candles) else None


def _bullish_signal_type(
    *,
    candle_range: float,
    body: float,
    upper_wick: float,
    lower_wick: float,
) -> SignalBarType | None:
    if body >= candle_range * 0.40:
        return "momentum"
    if lower_wick >= candle_range * 0.35 and lower_wick > upper_wick:
        if body >= candle_range * 0.10:
            return "rejection"
    return None


def _bearish_signal_type(
    *,
    candle_range: float,
    body: float,
    upper_wick: float,
    lower_wick: float,
) -> SignalBarType | None:
    if body >= candle_range * 0.40:
        return "momentum"
    if upper_wick >= candle_range * 0.35 and upper_wick > lower_wick:
        if body >= candle_range * 0.10:
            return "rejection"
    return None


def _evaluate_ema_context(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    context: TwoLeggedPullbackContext,
    *,
    config: TwoLeggedPullbackConfig,
) -> dict[str, object]:
    ema = context.ema_by_time.get(signal_bar.candle.ts_event)
    if ema is None:
        return {"enabled": config.use_ema_context, "passed": not config.use_ema_context}

    if signal_bar.side == "long":
        leg2_distance = abs(structure.leg2.leg_low_price - ema)
        signal_distance = abs(signal_bar.candle.low - ema)
        direction_passed = signal_bar.candle.close > ema
    else:
        leg2_distance = abs(structure.leg2.leg_high_price - ema)
        signal_distance = abs(signal_bar.candle.high - ema)
        direction_passed = signal_bar.candle.close < ema

    near_distance = min(leg2_distance, signal_distance)
    near_passed = near_distance <= config.ema_near_max_distance
    return {
        "enabled": config.use_ema_context,
        "passed": (near_passed and direction_passed) if config.use_ema_context else True,
        "ema": ema,
        "near_distance": near_distance,
        "near_passed": near_passed,
        "direction_passed": direction_passed,
    }


def _evaluate_vwap_context(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    context: TwoLeggedPullbackContext,
    *,
    config: TwoLeggedPullbackConfig,
) -> dict[str, object]:
    vwap = context.vwap_by_time.get(signal_bar.candle.ts_event)
    if vwap is None:
        return {"enabled": config.use_vwap_context, "passed": not config.use_vwap_context}

    if signal_bar.side == "long":
        leg2_distance = abs(structure.leg2.leg_low_price - vwap)
        signal_distance = abs(signal_bar.candle.low - vwap)
    else:
        leg2_distance = abs(structure.leg2.leg_high_price - vwap)
        signal_distance = abs(signal_bar.candle.high - vwap)

    near_distance = min(leg2_distance, signal_distance)
    near_passed = near_distance <= config.vwap_near_max_distance
    return {
        "enabled": config.use_vwap_context,
        "passed": near_passed if config.use_vwap_context else True,
        "vwap": vwap,
        "near_distance": near_distance,
        "near_passed": near_passed,
    }


def _evaluate_level_context(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    *,
    levels: dict[str, float] | None,
    max_distance: float,
) -> dict[str, object]:
    if not levels:
        return {"passed": False, "levels": None, "near_level": None}

    reference_prices = _context_reference_prices(structure, signal_bar)
    distances = {
        name: min(abs(reference - level) for reference in reference_prices)
        for name, level in levels.items()
    }
    near_level = min(distances, key=distances.get)
    return {
        "passed": distances[near_level] <= max_distance,
        "levels": levels,
        "distances": distances,
        "near_level": near_level,
    }


def _evaluate_premarket_context(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
    context: TwoLeggedPullbackContext,
    *,
    max_distance: float,
) -> dict[str, object]:
    if context.premarket_levels is None:
        return {"passed": False, "levels": None, "near_level": None}
    return _evaluate_level_context(
        structure,
        signal_bar,
        levels={
            "premarket_high": context.premarket_levels.high,
            "premarket_low": context.premarket_levels.low,
        },
        max_distance=max_distance,
    )


def _context_reference_prices(
    structure: TwoLeggedPullbackStructure,
    signal_bar: SignalBar,
) -> list[float]:
    if signal_bar.side == "long":
        return [structure.leg2.leg_low_price, signal_bar.candle.low]
    return [structure.leg2.leg_high_price, signal_bar.candle.high]


def _raw_leg_switch_count_near_signal(
    raw_legs: list[RawLeg],
    signal_bar: SignalBar,
    *,
    config: TwoLeggedPullbackConfig,
) -> int:
    lookback_start = signal_bar.candle.ts_event - _minutes(config.chop_lookback_bars)
    return sum(
        1
        for leg in raw_legs
        if leg.switch_bar_time is not None
        and lookback_start <= leg.switch_bar_time <= signal_bar.candle.ts_event
    )


def _anchor_metadata(anchor: AnchorRange | None) -> dict[str, object] | None:
    if anchor is None:
        return None
    return {
        "side": anchor.side,
        "anchor_high": anchor.anchor_high,
        "anchor_high_time": anchor.anchor_high_time.isoformat(),
        "anchor_low": anchor.anchor_low,
        "anchor_low_time": anchor.anchor_low_time.isoformat(),
        "anchor_range": anchor.anchor_range,
    }


def _legs_metadata(structure: TwoLeggedPullbackStructure) -> dict[str, object]:
    return {
        "leg1": _raw_leg_metadata(structure.leg1),
        "middle_move": _raw_leg_metadata(structure.middle_move),
        "leg2": _raw_leg_metadata(structure.leg2),
    }


def _raw_leg_metadata(leg: RawLeg) -> dict[str, object]:
    return {
        "leg_direction": leg.leg_direction,
        "status": leg.status,
        "start_bar_time": leg.start_bar_time.isoformat(),
        "start_price": leg.start_price,
        "end_bar_time": leg.end_bar_time.isoformat(),
        "bar_count": leg.bar_count,
        "leg_high_price": leg.leg_high_price,
        "leg_high_bar_time": leg.leg_high_bar_time.isoformat(),
        "leg_low_price": leg.leg_low_price,
        "leg_low_bar_time": leg.leg_low_bar_time.isoformat(),
        "switch_bar_time": leg.switch_bar_time.isoformat() if leg.switch_bar_time else None,
    }


def _signal_bar_metadata(signal_bar: SignalBar) -> dict[str, object]:
    candle = signal_bar.candle
    return {
        "signal_bar_time": candle.ts_event.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "signal_type": signal_bar.signal_type,
        "candle_range": signal_bar.candle_range,
        "body": signal_bar.body,
        "upper_wick": signal_bar.upper_wick,
        "lower_wick": signal_bar.lower_wick,
    }


def _context_metadata(
    context: TwoLeggedPullbackContext,
    signal_time: datetime,
) -> dict[str, object]:
    return {
        "ema20_at_signal": context.ema_by_time.get(signal_time),
        "vwap_at_signal": context.vwap_by_time.get(signal_time),
        "previous_day_levels": context.previous_day_levels,
        "premarket_levels": (
            {
                "premarket_high": context.premarket_levels.high,
                "premarket_low": context.premarket_levels.low,
            }
            if context.premarket_levels
            else None
        ),
    }


def _ema_by_time(candles: list[BacktestCandle], *, length: int) -> dict[datetime, float]:
    if not candles:
        return {}
    multiplier = 2 / (length + 1)
    ema = candles[0].close
    values = {candles[0].ts_event: ema}
    for candle in candles[1:]:
        ema = (candle.close - ema) * multiplier + ema
        values[candle.ts_event] = ema
    return values


def _vwap_by_time(candles: list[BacktestCandle]) -> dict[datetime, float]:
    values: dict[datetime, float] = {}
    cumulative_price_volume = 0.0
    cumulative_volume = 0
    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / 3
        cumulative_price_volume += typical_price * candle.volume
        cumulative_volume += candle.volume
        values[candle.ts_event] = (
            cumulative_price_volume / cumulative_volume if cumulative_volume else candle.close
        )
    return values


def _premarket_levels(
    candles: list[BacktestCandle],
    *,
    config: TwoLeggedPullbackConfig,
) -> PremarketLevels | None:
    premarket_candles = [
        candle
        for candle in candles
        if config.premarket_warmup_start <= _ct_time(candle) < TRADING_START_CT
    ]
    if not premarket_candles:
        return None
    return PremarketLevels(
        high=max(candle.high for candle in premarket_candles),
        low=min(candle.low for candle in premarket_candles),
    )


def _previous_day_levels(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    required = ("high", "low", "close")
    if not all(key in value for key in required):
        return None
    return {key: float(value[key]) for key in required}


def _require_positive_int(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be positive.")


def _require_non_negative_int(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative.")


def _require_positive_float(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive.")


def _require_non_negative_float(name: str, value: float) -> None:
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be non-negative.")


def _bool_parameter(values: dict[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _float_parameter(values: dict[str, Any], key: str, default: float) -> float:
    return float(values.get(key, default))


def _int_parameter(values: dict[str, Any], key: str, default: int) -> int:
    return int(values.get(key, default))


def _minutes(value: int):
    return timedelta(minutes=value)


def _ct_trade_date(candle: BacktestCandle) -> date:
    return candle.ts_event.astimezone(CENTRAL_TIME).date()


def _ct_time(candle: BacktestCandle) -> time:
    return candle.ts_event.astimezone(CENTRAL_TIME).time()


def _ct_datetime(trade_date: date, ct_time: time) -> datetime:
    return datetime.combine(trade_date, ct_time, tzinfo=CENTRAL_TIME).astimezone(UTC)
