"""Validation rules for clean OHLCV market-data rows."""

from __future__ import annotations

from datetime import UTC

from shared_core.market_data.clean.schema import CleanOhlcvBar


class CleanOhlcvValidationError(ValueError):
    """Raised when clean OHLCV rows fail validation."""


def validate_clean_ohlcv(rows: list[CleanOhlcvBar], *, expected_timeframe: str) -> None:
    """Validate clean OHLCV rows before they are stored."""
    if not rows:
        raise CleanOhlcvValidationError("Clean OHLCV rows must not be empty.")

    seen_keys: set[tuple[str, str, object]] = set()
    previous_ts = None

    for row in rows:
        _validate_required(row)
        if row.timeframe != expected_timeframe:
            raise CleanOhlcvValidationError("Clean OHLCV timeframe does not match partition.")
        if row.ts_event.tzinfo is None or row.ts_event.utcoffset() != UTC.utcoffset(row.ts_event):
            raise CleanOhlcvValidationError("Clean OHLCV ts_event must be timezone-aware UTC.")
        if row.session_date != row.ts_event.date():
            raise CleanOhlcvValidationError("Clean OHLCV session_date must match ts_event date.")
        if min(row.open, row.high, row.low, row.close) <= 0:
            raise CleanOhlcvValidationError("Clean OHLCV prices must be positive.")
        if row.high < row.low:
            raise CleanOhlcvValidationError(
                "Clean OHLCV high must be greater than or equal to low."
            )
        if row.high < row.open or row.high < row.close:
            raise CleanOhlcvValidationError("Clean OHLCV high must be at least open and close.")
        if row.low > row.open or row.low > row.close:
            raise CleanOhlcvValidationError("Clean OHLCV low must be at most open and close.")
        if row.volume < 0:
            raise CleanOhlcvValidationError("Clean OHLCV volume must be non-negative.")

        key = (row.symbol, row.timeframe, row.ts_event)
        if key in seen_keys:
            raise CleanOhlcvValidationError("Clean OHLCV rows contain duplicate timestamps.")
        seen_keys.add(key)

        if previous_ts is not None and row.ts_event < previous_ts:
            raise CleanOhlcvValidationError("Clean OHLCV timestamps must be sorted.")
        previous_ts = row.ts_event


def _validate_required(row: CleanOhlcvBar) -> None:
    if not row.symbol:
        raise CleanOhlcvValidationError("Clean OHLCV symbol is required.")
    if row.ts_event is None:
        raise CleanOhlcvValidationError("Clean OHLCV ts_event is required.")
    if row.session_date is None:
        raise CleanOhlcvValidationError("Clean OHLCV session_date is required.")
    if not row.source_vendor or not row.source_dataset or not row.source_schema:
        raise CleanOhlcvValidationError("Clean OHLCV source metadata is required.")
