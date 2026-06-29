"""Dagster definitions for tradebox pipelines."""

from dagster import Definitions

from pipelines.assets import (
    clean_market_data_partition,
    market_data_request_plan,
    placeholder_asset,
    raw_market_data_partition,
    spy_raw_to_clean_existing_sample,
)
from pipelines.jobs import safe_market_data_pipeline_job, spy_raw_to_clean_job

defs = Definitions(
    assets=[
        placeholder_asset,
        market_data_request_plan,
        raw_market_data_partition,
        clean_market_data_partition,
        spy_raw_to_clean_existing_sample,
    ],
    jobs=[safe_market_data_pipeline_job, spy_raw_to_clean_job],
)
