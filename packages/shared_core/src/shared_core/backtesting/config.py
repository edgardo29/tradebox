"""Backtest request configuration and guardrails."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

MAX_LOCAL_BACKTEST_WINDOW = timedelta(days=7)
DEFAULT_INITIAL_CAPITAL = 100_000.0


class BacktestConfigError(ValueError):
    """Raised when a backtest config is invalid."""


@dataclass(frozen=True)
class BacktestConfig:
    """Validated, reusable backtest configuration."""

    symbol: str
    timeframe: str
    start: datetime
    end: datetime
    clean_data_partition_id: uuid.UUID
    strategy_name: str
    strategy_version: str
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        symbol: str,
        timeframe: str,
        start: str | datetime,
        end: str | datetime,
        clean_data_partition_id: str | uuid.UUID,
        strategy_name: str,
        strategy_version: str = "0.1.0",
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        parameters: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> BacktestConfig:
        """Build and validate a backtest config."""

        config = cls(
            symbol=_normalize_non_empty("symbol", symbol).upper(),
            timeframe=_normalize_non_empty("timeframe", timeframe),
            start=_parse_datetime("start", start),
            end=_parse_datetime("end", end),
            clean_data_partition_id=_parse_uuid(clean_data_partition_id),
            strategy_name=_normalize_non_empty("strategy_name", strategy_name),
            strategy_version=_normalize_non_empty("strategy_version", strategy_version),
            initial_capital=float(initial_capital),
            parameters=dict(parameters or {}),
            metadata=dict(metadata or {}),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Validate guardrails for local/dev backtests."""

        if self.start >= self.end:
            raise BacktestConfigError("Backtest start must be before end.")
        if self.end - self.start > MAX_LOCAL_BACKTEST_WINDOW:
            raise BacktestConfigError(
                "Backtest date range is too broad for local/dev runs. "
                f"Use {MAX_LOCAL_BACKTEST_WINDOW.days} days or less."
            )
        if self.initial_capital <= 0:
            raise BacktestConfigError("Backtest initial capital must be positive.")

    def to_snapshot(self) -> dict[str, Any]:
        """Return a reproducible config snapshot for persistence."""

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "clean_data_partition_id": str(self.clean_data_partition_id),
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "initial_capital": self.initial_capital,
            "parameters": self.parameters,
            "metadata": self.metadata,
        }

    def strategy_config_hash(self) -> str:
        """Hash the strategy/config snapshot for run reproducibility."""

        payload = json.dumps(self.to_snapshot(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_datetime(field_name: str, value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise BacktestConfigError(f"Backtest {field_name} must be a datetime.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise BacktestConfigError("Backtest clean data partition id is required.") from exc


def _normalize_non_empty(field_name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise BacktestConfigError(f"Backtest {field_name} is required.")
    return normalized
