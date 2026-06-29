from datetime import UTC, datetime, timedelta

import pytest

from shared_core.market_data import (
    ALLOW_LIVE_DATABENTO_ENV_VAR,
    EXISTING_SAMPLE_MODE,
    LIVE_DATABENTO_MODE,
    MarketDataRequestConfig,
    MarketDataRequestConfigError,
)


def test_default_market_data_request_uses_existing_sample_mode() -> None:
    request = MarketDataRequestConfig.create()

    assert request.symbol == "SPY"
    assert request.vendor == "databento"
    assert request.dataset == "EQUS.MINI"
    assert request.source_schema == "ohlcv-1m"
    assert request.timeframe == "1m"
    assert request.session_date.isoformat() == "2024-01-02"
    assert request.mode == EXISTING_SAMPLE_MODE
    assert request.allow_live_databento_request is False
    assert request.uses_live_databento is False


def test_live_databento_mode_requires_explicit_approval() -> None:
    with pytest.raises(MarketDataRequestConfigError, match=ALLOW_LIVE_DATABENTO_ENV_VAR):
        MarketDataRequestConfig.create(mode=LIVE_DATABENTO_MODE)


def test_live_databento_mode_can_be_explicitly_approved() -> None:
    request = MarketDataRequestConfig.create(
        mode=LIVE_DATABENTO_MODE,
        allow_live_databento_request=True,
    )

    assert request.uses_live_databento is True
    assert request.to_metadata()["live_databento_used"] == "true"


@pytest.mark.parametrize("symbol", ["SPY,QQQ", "SPY QQQ", "SPY;QQQ", "SPY|QQQ"])
def test_market_data_request_rejects_symbol_lists(symbol: str) -> None:
    with pytest.raises(MarketDataRequestConfigError, match="symbol lists"):
        MarketDataRequestConfig.create(symbol=symbol)


def test_market_data_request_rejects_broad_date_ranges() -> None:
    start = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)

    with pytest.raises(MarketDataRequestConfigError, match="too broad"):
        MarketDataRequestConfig.create(start=start, end=start + timedelta(minutes=6))


def test_market_data_request_rejects_mismatched_timeframe_and_schema() -> None:
    with pytest.raises(MarketDataRequestConfigError, match="timeframe"):
        MarketDataRequestConfig.create(source_schema="ohlcv-1m", timeframe="5m")


def test_market_data_request_loads_from_env_values() -> None:
    request = MarketDataRequestConfig.from_env(
        {
            "MARKET_DATA_SYMBOL": "qqq",
            "MARKET_DATA_MODE": EXISTING_SAMPLE_MODE,
            "MARKET_DATA_LIMIT": "1",
        }
    )

    assert request.symbol == "QQQ"
    assert request.mode == EXISTING_SAMPLE_MODE


def test_market_data_request_round_trips_from_metadata() -> None:
    request = MarketDataRequestConfig.create(symbol="qqq")

    assert MarketDataRequestConfig.from_mapping(request.to_metadata()) == request
