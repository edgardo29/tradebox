import pytest

from shared_core.storage.object_keys import (
    DEV_SMOKE_TEST_PREFIX,
    build_object_key,
    clean_ohlcv_object_key,
    ensure_key_prefix,
    market_data_partition_key,
    raw_market_data_object_key,
    smoke_test_object_key,
)


def test_build_object_key_normalizes_path_parts() -> None:
    assert build_object_key("/raw/", "databento", "/equities/trades/", "AAPL.dbn") == (
        "raw/databento/equities/trades/AAPL.dbn"
    )


def test_build_object_key_rejects_empty_parts() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        build_object_key("dev", " ")


def test_build_object_key_rejects_relative_segments() -> None:
    with pytest.raises(ValueError, match="relative path"):
        build_object_key("dev", "../secret.txt")


def test_ensure_key_prefix_adds_trailing_slash() -> None:
    assert ensure_key_prefix("/dev/smoke-tests") == DEV_SMOKE_TEST_PREFIX


def test_smoke_test_object_key_uses_dev_prefix() -> None:
    assert smoke_test_object_key("check.txt") == "dev/smoke-tests/check.txt"


def test_clean_ohlcv_object_key_uses_partitioned_path() -> None:
    assert clean_ohlcv_object_key(
        vendor="databento",
        dataset="EQUS.MINI",
        symbol="SPY",
        timeframe="1m",
        session_date="2024-01-02",
    ) == (
        "clean/vendor=databento/dataset=EQUS.MINI/symbol=SPY/timeframe=1m/"
        "session_date=2024-01-02/part-000.parquet"
    )


def test_raw_market_data_object_key_uses_partitioned_path() -> None:
    assert raw_market_data_object_key(
        vendor="databento",
        dataset="EQUS.MINI",
        symbol="SPY",
        source_schema="ohlcv-1m",
        session_date="2024-01-02",
        run_id="abc123",
    ) == (
        "raw/vendor=databento/dataset=EQUS.MINI/symbol=SPY/schema=ohlcv-1m/"
        "session_date=2024-01-02/abc123.dbn.zst"
    )


def test_market_data_partition_key_is_stable() -> None:
    assert market_data_partition_key(
        vendor="databento",
        dataset="EQUS.MINI",
        symbol="SPY",
        timeframe="1m",
        session_date="2024-01-02",
    ) == "vendor=databento|dataset=EQUS.MINI|symbol=SPY|timeframe=1m|session_date=2024-01-02"
