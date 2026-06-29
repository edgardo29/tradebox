"""Databento configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ


class DatabentoConfigError(ValueError):
    """Raised when required Databento configuration is missing."""


@dataclass(frozen=True)
class DatabentoConfig:
    """Configuration required for future Databento client calls."""

    api_key: str = field(repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> DatabentoConfig:
        source = environ if env is None else env
        api_key = source.get("DATABENTO_API_KEY", "").strip()
        if not api_key or "<" in api_key or ">" in api_key:
            raise DatabentoConfigError(
                "Missing Databento environment variable: DATABENTO_API_KEY. "
                "Set it in your local environment or .env before running live Databento commands."
            )
        return cls(api_key=api_key)


def load_databento_config_from_env(env: Mapping[str, str] | None = None) -> DatabentoConfig:
    """Load Databento config from environment variables."""
    return DatabentoConfig.from_env(env)
