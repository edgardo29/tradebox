"""Dagster wrapper for the local SPY raw-to-clean vertical slice."""

from __future__ import annotations

import os
from collections.abc import Mapping

from dagster import MetadataValue, asset
from tradebox_workflows import raw_databento_partition_to_clean

ALLOW_LIVE_DATABENTO_ENV_VAR = "ALLOW_LIVE_DATABENTO_REQUEST"
SPY_RAW_TO_CLEAN_ASSET_NAME = "spy_raw_to_clean_existing_sample"

_EXPECTED_METADATA_KEYS = {
    "partition_id",
    "instrument_symbol",
    "raw_object_path",
    "clean_object_path",
    "clean_file_format",
    "row_count",
    "validation_error_count",
    "partition_status",
    "clean_content_hash",
}


@asset(
    name=SPY_RAW_TO_CLEAN_ASSET_NAME,
    description=(
        "Runs the existing local SPY raw-to-clean smoke conversion against the raw R2 sample. "
        "This asset does not make Databento requests."
    ),
    group_name="market_data_smoke",
)
def spy_raw_to_clean_existing_sample(context) -> dict[str, object]:
    """Run the shared raw-to-clean workflow and attach partition metadata to Dagster."""

    if live_databento_enabled():
        raise RuntimeError(
            f"{ALLOW_LIVE_DATABENTO_ENV_VAR}=true is not supported by this Dagster wrapper. "
            "Use existing-sample mode here so the job cannot spend Databento credits."
        )

    result = run_spy_raw_to_clean_workflow()
    context.add_output_metadata(_dagster_metadata(result))
    context.log.info(
        "SPY raw-to-clean wrapper completed with partition_status=%s row_count=%s",
        result.get("partition_status"),
        result.get("row_count"),
    )
    return result


def live_databento_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether live Databento requests were explicitly enabled."""

    source = os.environ if env is None else env
    return source.get(ALLOW_LIVE_DATABENTO_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def run_spy_raw_to_clean_workflow() -> dict[str, object]:
    """Run the shared raw-to-clean workflow for SPY."""

    return raw_databento_partition_to_clean(symbol="SPY")


def _dagster_metadata(values: Mapping[str, object]) -> dict[str, MetadataValue]:
    return {
        key: MetadataValue.text(str(value))
        for key, value in values.items()
        if key in _EXPECTED_METADATA_KEYS and value
    }
