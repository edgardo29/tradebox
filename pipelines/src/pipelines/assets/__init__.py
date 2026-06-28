"""Placeholder Dagster assets.

These assets mark future pipeline stages without implementing Databento, R2,
Parquet, scanner, strategy, or backtesting logic yet.
"""

from dagster import asset


@asset
def placeholder_asset() -> str:
    """Placeholder asset for the initial Dagster pipeline scaffold."""

    return "tradebox pipeline placeholder"
