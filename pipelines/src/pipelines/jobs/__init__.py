"""Dagster job definitions."""

from dagster import AssetSelection, define_asset_job

from pipelines.assets import (
    clean_market_data_partition,
    market_data_request_plan,
    raw_market_data_partition,
    spy_raw_to_clean_existing_sample,
)

safe_market_data_pipeline_job = define_asset_job(
    name="safe_market_data_pipeline_job",
    selection=AssetSelection.assets(
        market_data_request_plan,
        raw_market_data_partition,
        clean_market_data_partition,
    ),
    description=(
        "Runs the guarded market-data pipeline in safe existing-sample mode by default. "
        "Live Databento mode requires explicit environment approval."
    ),
)

spy_raw_to_clean_job = define_asset_job(
    name="spy_raw_to_clean_job",
    selection=AssetSelection.assets(spy_raw_to_clean_existing_sample),
    description=(
        "Runs the local SPY raw-to-clean wrapper against the existing raw sample. "
        "This job does not make Databento requests."
    ),
)

__all__ = ["safe_market_data_pipeline_job", "spy_raw_to_clean_job"]
