"""Dagster definitions for tradebox pipelines."""

from dagster import Definitions

from pipelines.assets import placeholder_asset

defs = Definitions(assets=[placeholder_asset])
