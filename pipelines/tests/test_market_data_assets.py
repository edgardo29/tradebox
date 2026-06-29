from __future__ import annotations

from shared_core.market_data import (
    ALLOW_LIVE_DATABENTO_ENV_VAR,
    EXISTING_SAMPLE_MODE,
    LIVE_DATABENTO_MODE,
    MarketDataRequestConfig,
)

from pipelines.assets.market_data import (
    convert_clean_market_data_partition,
    load_market_data_request_plan,
    resolve_raw_market_data_partition,
)


def test_load_market_data_request_plan_defaults_to_existing_sample() -> None:
    request = load_market_data_request_plan({})

    assert request.symbol == "SPY"
    assert request.mode == EXISTING_SAMPLE_MODE
    assert request.uses_live_databento is False


def test_default_raw_partition_resolution_uses_existing_partition_workflow() -> None:
    request = MarketDataRequestConfig.create()
    calls: list[dict[str, object]] = []

    def fake_existing_resolver(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "partition_id": "abc",
            "instrument_symbol": "SPY",
            "dataset": "smoke_test",
            "raw_object_path": "dev/databento-smoke-tests/raw/sample.dbn.zst",
            "partition_status": "raw_available",
        }

    result = resolve_raw_market_data_partition(
        request,
        existing_partition_resolver=fake_existing_resolver,
    )

    assert result["mode"] == EXISTING_SAMPLE_MODE
    assert result["live_databento_used"] == "false"
    assert result["dataset"] == "EQUS.MINI"
    assert result["catalog_dataset"] == "smoke_test"
    assert result["raw_object_path"] == "dev/databento-smoke-tests/raw/sample.dbn.zst"
    assert calls == [
        {
            "symbol": "SPY",
            "vendor": "databento",
            "timeframe": "1m",
            "session_date": request.session_date,
        }
    ]


def test_live_raw_partition_resolution_requires_explicit_config() -> None:
    try:
        MarketDataRequestConfig.create(mode=LIVE_DATABENTO_MODE)
    except Exception as exc:
        assert ALLOW_LIVE_DATABENTO_ENV_VAR in str(exc)
    else:
        raise AssertionError("Expected live mode to require explicit approval.")


def test_live_raw_partition_resolution_uses_databento_workflow_when_approved() -> None:
    request = MarketDataRequestConfig.create(
        mode=LIVE_DATABENTO_MODE,
        allow_live_databento_request=True,
    )
    calls: list[dict[str, object]] = []

    def fake_live_ingestor(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append({"args": args, "kwargs": kwargs})
        return {
            "data_partition_id": "abc",
            "symbol": "SPY",
            "dataset": "EQUS.MINI",
            "raw_object_path": "raw/path.dbn.zst",
        }

    result = resolve_raw_market_data_partition(
        request,
        live_partition_ingestor=fake_live_ingestor,
    )

    assert result["partition_id"] == "abc"
    assert result["live_databento_used"] == "true"
    assert calls[0]["kwargs"] == {"confirm_credit_use": True}
    assert calls[0]["args"][0].symbol == "SPY"


def test_clean_partition_conversion_uses_shared_workflow() -> None:
    request = MarketDataRequestConfig.create()
    calls: list[dict[str, object]] = []

    def fake_converter(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "partition_id": "abc",
            "instrument_symbol": "SPY",
            "clean_object_path": "clean/path.parquet",
            "row_count": 1,
            "partition_status": "validated",
        }

    result = convert_clean_market_data_partition(
        request,
        request.to_metadata(),
        converter=fake_converter,
    )

    assert result["clean_object_path"] == "clean/path.parquet"
    assert result["partition_status"] == "validated"
    assert calls == [{"symbol": "SPY"}]


def test_workflow_failures_are_not_swallowed() -> None:
    request = MarketDataRequestConfig.create()

    def failing_existing_resolver(**_: object) -> dict[str, object]:
        raise RuntimeError("boom")

    try:
        resolve_raw_market_data_partition(
            request,
            existing_partition_resolver=failing_existing_resolver,
        )
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("Expected workflow failure to be raised.")
