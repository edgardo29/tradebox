from dataclasses import replace
from datetime import UTC, datetime

import pytest

from shared_core.market_data.clean.schema import CleanOhlcvBar
from shared_core.market_data.clean.validation import CleanOhlcvValidationError, validate_clean_ohlcv


def test_validate_clean_ohlcv_accepts_valid_rows() -> None:
    validate_clean_ohlcv([_bar()], expected_timeframe="1m")


def test_validate_clean_ohlcv_rejects_bad_price_relationships() -> None:
    with pytest.raises(CleanOhlcvValidationError, match="high"):
        validate_clean_ohlcv([replace(_bar(), high=471.0)], expected_timeframe="1m")


def test_validate_clean_ohlcv_rejects_negative_volume() -> None:
    with pytest.raises(CleanOhlcvValidationError, match="volume"):
        validate_clean_ohlcv([replace(_bar(), volume=-1)], expected_timeframe="1m")


def test_validate_clean_ohlcv_rejects_duplicate_timestamp() -> None:
    bar = _bar()

    with pytest.raises(CleanOhlcvValidationError, match="duplicate"):
        validate_clean_ohlcv([bar, bar], expected_timeframe="1m")


def test_validate_clean_ohlcv_rejects_unsorted_timestamps() -> None:
    first = _bar(ts_event=datetime(2024, 1, 2, 14, 31, tzinfo=UTC))
    second = _bar(ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC))

    with pytest.raises(CleanOhlcvValidationError, match="sorted"):
        validate_clean_ohlcv([first, second], expected_timeframe="1m")


def _bar(ts_event: datetime = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)) -> CleanOhlcvBar:
    return CleanOhlcvBar(
        symbol="SPY",
        ts_event=ts_event,
        session_date=ts_event.date(),
        timeframe="1m",
        open=472.18,
        high=472.65,
        low=472.06,
        close=472.52,
        volume=47_609,
        source_vendor="databento",
        source_dataset="EQUS.MINI",
        source_schema="ohlcv-1m",
        processed_at=datetime(2026, 6, 28, 12, tzinfo=UTC),
    )
