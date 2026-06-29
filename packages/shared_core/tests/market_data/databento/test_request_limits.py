from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from shared_core.market_data.databento.request_limits import (
    DatabentoSmokeRequest,
    DatabentoSmokeRequestError,
    databento_smoke_raw_object_key,
    normalize_single_symbol,
)


def test_default_spy_smoke_request_is_tiny() -> None:
    request = DatabentoSmokeRequest.create()

    assert request.symbol == "SPY"
    assert request.dataset == "EQUS.MINI"
    assert request.schema == "ohlcv-1m"
    assert request.timeframe == "1m"
    assert request.limit == 1
    assert request.end - request.start == timedelta(minutes=1)


def test_smoke_request_allows_one_non_spy_symbol() -> None:
    request = DatabentoSmokeRequest.create(symbol="qqq")

    assert request.symbol == "QQQ"


@pytest.mark.parametrize("symbol", ["SPY,QQQ", "SPY QQQ", "SPY;QQQ", "SPY|QQQ"])
def test_normalize_single_symbol_rejects_symbol_lists(symbol: str) -> None:
    with pytest.raises(DatabentoSmokeRequestError, match="symbol lists"):
        normalize_single_symbol(symbol)


def test_smoke_request_rejects_broad_date_ranges() -> None:
    with pytest.raises(DatabentoSmokeRequestError, match="too broad"):
        DatabentoSmokeRequest.create(
            start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
            end=datetime(2024, 1, 2, 14, 36, tzinfo=UTC),
        )


def test_smoke_request_rejects_large_limits() -> None:
    with pytest.raises(DatabentoSmokeRequestError, match="record limit"):
        DatabentoSmokeRequest.create(limit=11)


def test_databento_smoke_raw_object_key_is_symbol_general() -> None:
    request = DatabentoSmokeRequest.create(symbol="qqq")
    run_id = UUID("11111111-2222-3333-4444-555555555555")

    assert databento_smoke_raw_object_key(request, run_id) == (
        "dev/databento-smoke-tests/raw/EQUS.MINI/QQQ/ohlcv-1m/2024-01-02/"
        "11111111222233334444555555555555.dbn.zst"
    )
