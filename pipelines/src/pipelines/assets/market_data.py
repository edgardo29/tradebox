"""Dagster assets for the guarded market-data pipeline foundation."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from dagster import MetadataValue, asset
from shared_core.market_data import (
    EXISTING_SAMPLE_MODE,
    LIVE_DATABENTO_MODE,
    MarketDataRequestConfig,
)
from tradebox_workflows import (
    describe_existing_raw_market_data_partition,
    ingest_databento_smoke_partition,
    raw_databento_partition_to_clean,
)

_DAGSTER_METADATA_KEYS = {
    "symbol",
    "vendor",
    "dataset",
    "catalog_dataset",
    "source_schema",
    "timeframe",
    "session_date",
    "start",
    "end",
    "mode",
    "live_databento_used",
    "partition_id",
    "data_partition_id",
    "instrument_id",
    "instrument_symbol",
    "raw_object_path",
    "clean_object_path",
    "raw_file_format",
    "clean_file_format",
    "row_count",
    "record_count",
    "validation_error_count",
    "partition_status",
}

MARKET_DATA_REQUEST_PLAN_ASSET_NAME = "market_data_request_plan"
RAW_MARKET_DATA_PARTITION_ASSET_NAME = "raw_market_data_partition"
CLEAN_MARKET_DATA_PARTITION_ASSET_NAME = "clean_market_data_partition"

ExistingPartitionResolver = Callable[..., Mapping[str, object]]
LivePartitionIngestor = Callable[..., Mapping[str, object]]
CleanPartitionConverter = Callable[..., Mapping[str, object]]


@asset(
    name=MARKET_DATA_REQUEST_PLAN_ASSET_NAME,
    group_name="market_data",
    description="Builds a guarded market-data request plan. Defaults to existing-sample mode.",
)
def market_data_request_plan(context) -> dict[str, str]:
    """Create a safe default request plan from environment configuration."""

    request = load_market_data_request_plan()
    metadata = request.to_metadata()
    context.add_output_metadata(_dagster_metadata(metadata))
    context.log.info(
        "Market-data request plan created for symbol=%s mode=%s live_databento_used=%s",
        request.symbol,
        request.mode,
        request.uses_live_databento,
    )
    return metadata


@asset(
    name=RAW_MARKET_DATA_PARTITION_ASSET_NAME,
    group_name="market_data",
    description="Resolves an existing raw partition or runs an explicitly approved live ingest.",
)
def raw_market_data_partition(
    context,
    market_data_request_plan: dict[str, str],
) -> dict[str, object]:
    """Resolve raw market-data metadata without making live requests by default."""

    request = MarketDataRequestConfig.from_mapping(market_data_request_plan)
    result = resolve_raw_market_data_partition(request)
    context.add_output_metadata(_dagster_metadata(result))
    context.log.info(
        "Raw market-data partition resolved for symbol=%s mode=%s raw_object_path=%s",
        result.get("symbol"),
        result.get("mode"),
        result.get("raw_object_path"),
    )
    return result


@asset(
    name=CLEAN_MARKET_DATA_PARTITION_ASSET_NAME,
    group_name="market_data",
    description="Converts the resolved raw partition into clean Parquet and updates metadata.",
)
def clean_market_data_partition(
    context,
    raw_market_data_partition: dict[str, object],
) -> dict[str, object]:
    """Run the existing raw-to-clean conversion for the resolved request plan."""

    request = MarketDataRequestConfig.from_mapping(raw_market_data_partition)
    result = convert_clean_market_data_partition(request, raw_market_data_partition)
    context.add_output_metadata(_dagster_metadata(result))
    context.log.info(
        "Clean market-data partition completed for symbol=%s status=%s row_count=%s",
        result.get("symbol"),
        result.get("partition_status"),
        result.get("row_count"),
    )
    return result


def load_market_data_request_plan(
    env: Mapping[str, str] | None = None,
) -> MarketDataRequestConfig:
    """Load the request plan from env values, defaulting to safe existing-sample mode."""

    return MarketDataRequestConfig.from_env(os.environ if env is None else env)


def resolve_raw_market_data_partition(
    request: MarketDataRequestConfig,
    *,
    existing_partition_resolver: ExistingPartitionResolver = (
        describe_existing_raw_market_data_partition
    ),
    live_partition_ingestor: LivePartitionIngestor = ingest_databento_smoke_partition,
) -> dict[str, object]:
    """Resolve raw partition metadata using the configured request mode."""

    if request.mode == EXISTING_SAMPLE_MODE:
        raw_metadata = existing_partition_resolver(
            symbol=request.symbol,
            vendor=request.vendor,
            timeframe=request.timeframe,
            session_date=request.session_date,
        )
        return _merge_request_and_script_metadata(request, raw_metadata, live_databento_used=False)

    if request.mode == LIVE_DATABENTO_MODE:
        raw_metadata = ingest_live_databento_partition(request, ingestor=live_partition_ingestor)
        return _merge_request_and_script_metadata(request, raw_metadata, live_databento_used=True)

    raise RuntimeError(f"Unsupported market-data request mode: {request.mode}")


def ingest_live_databento_partition(
    request: MarketDataRequestConfig,
    *,
    ingestor: LivePartitionIngestor = ingest_databento_smoke_partition,
) -> Mapping[str, object]:
    """Run the live Databento smoke workflow after shared_core guardrails approve it."""

    if not request.uses_live_databento or not request.allow_live_databento_request:
        raise RuntimeError("Live Databento ingest requires explicit approval.")

    return ingestor(
        request.to_databento_request(),
        confirm_credit_use=request.allow_live_databento_request,
    )


def convert_clean_market_data_partition(
    request: MarketDataRequestConfig,
    raw_metadata: Mapping[str, object],
    *,
    converter: CleanPartitionConverter = raw_databento_partition_to_clean,
) -> dict[str, object]:
    """Convert the resolved raw partition to clean Parquet."""

    clean_metadata = converter(symbol=request.symbol)
    return {
        **raw_metadata,
        **_normalize_script_metadata(clean_metadata),
        "live_databento_used": str(request.uses_live_databento).lower(),
    }


def _merge_request_and_script_metadata(
    request: MarketDataRequestConfig,
    script_metadata: Mapping[str, object],
    *,
    live_databento_used: bool,
) -> dict[str, object]:
    return {
        **request.to_metadata(),
        **_normalize_script_metadata(script_metadata),
        "live_databento_used": str(live_databento_used).lower(),
    }


def _normalize_script_metadata(values: Mapping[str, object]) -> dict[str, object]:
    normalized = dict(values)
    if "data_partition_id" in normalized and "partition_id" not in normalized:
        normalized["partition_id"] = normalized["data_partition_id"]
    if "dataset" in normalized:
        normalized["catalog_dataset"] = normalized.pop("dataset")
    return normalized


def _dagster_metadata(values: Mapping[str, object]) -> dict[str, MetadataValue]:
    return {
        key: MetadataValue.text(str(value))
        for key, value in values.items()
        if key in _DAGSTER_METADATA_KEYS and value not in {None, ""}
    }
