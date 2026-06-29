"""Dagster assets for tradebox pipelines."""

from dagster import asset

from pipelines.assets.market_data import (
    clean_market_data_partition,
    market_data_request_plan,
    raw_market_data_partition,
)
from pipelines.assets.spy_raw_to_clean import spy_raw_to_clean_existing_sample


@asset
def placeholder_asset() -> str:
    """Placeholder asset for the initial Dagster pipeline scaffold."""

    return "tradebox pipeline placeholder"


__all__ = [
    "clean_market_data_partition",
    "market_data_request_plan",
    "placeholder_asset",
    "raw_market_data_partition",
    "spy_raw_to_clean_existing_sample",
]
