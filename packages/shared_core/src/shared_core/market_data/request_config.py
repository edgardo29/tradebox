"""Reusable market-data request configuration and guardrails."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from shared_core.market_data.databento.request_limits import (
    DEFAULT_DATABENTO_DATASET,
    DEFAULT_DATABENTO_LIMIT,
    DEFAULT_DATABENTO_SCHEMA,
    DEFAULT_DATABENTO_STYPE_IN,
    DEFAULT_SPY_SMOKE_REQUEST,
    DatabentoSmokeRequest,
    DatabentoSmokeRequestError,
)

ALLOW_LIVE_DATABENTO_ENV_VAR = "ALLOW_LIVE_DATABENTO_REQUEST"
EXISTING_SAMPLE_MODE = "existing_sample"
LIVE_DATABENTO_MODE = "live_databento"
DEFAULT_MARKET_DATA_VENDOR = "databento"
DEFAULT_MARKET_DATA_TIMEFRAME = "1m"


class MarketDataRequestConfigError(ValueError):
    """Raised when a market-data request violates pipeline guardrails."""


@dataclass(frozen=True)
class MarketDataRequestConfig:
    """Validated request plan for controlled market-data ingestion and cleaning."""

    symbol: str
    vendor: str
    dataset: str
    source_schema: str
    timeframe: str
    start: datetime
    end: datetime
    session_date: date
    mode: str
    allow_live_databento_request: bool
    stype_in: str
    limit: int

    @classmethod
    def create(
        cls,
        *,
        symbol: str = DEFAULT_SPY_SMOKE_REQUEST["symbol"],
        vendor: str = DEFAULT_MARKET_DATA_VENDOR,
        dataset: str = DEFAULT_DATABENTO_DATASET,
        source_schema: str = DEFAULT_DATABENTO_SCHEMA,
        timeframe: str | None = None,
        start: str | datetime = DEFAULT_SPY_SMOKE_REQUEST["start"],
        end: str | datetime = DEFAULT_SPY_SMOKE_REQUEST["end"],
        mode: str = EXISTING_SAMPLE_MODE,
        allow_live_databento_request: bool | str = False,
        stype_in: str = DEFAULT_DATABENTO_STYPE_IN,
        limit: int | str = DEFAULT_DATABENTO_LIMIT,
    ) -> MarketDataRequestConfig:
        """Build and validate a request plan."""

        normalized_mode = _normalize_mode(mode)
        allow_live = parse_bool(allow_live_databento_request)
        normalized_vendor = _normalize_non_empty("vendor", vendor).lower()
        normalized_limit = _parse_int("limit", limit)

        try:
            databento_request = DatabentoSmokeRequest.create(
                symbol=symbol,
                start=start,
                end=end,
                dataset=dataset,
                schema=source_schema,
                stype_in=stype_in,
                limit=normalized_limit,
            )
        except DatabentoSmokeRequestError as exc:
            raise MarketDataRequestConfigError(str(exc)) from exc

        resolved_timeframe = timeframe or databento_request.timeframe
        if resolved_timeframe != databento_request.timeframe:
            raise MarketDataRequestConfigError(
                "Market-data timeframe must match the requested source schema."
            )

        if normalized_mode == LIVE_DATABENTO_MODE and not allow_live:
            raise MarketDataRequestConfigError(
                f"{LIVE_DATABENTO_MODE} mode requires {ALLOW_LIVE_DATABENTO_ENV_VAR}=true."
            )

        return cls(
            symbol=databento_request.symbol,
            vendor=normalized_vendor,
            dataset=databento_request.dataset,
            source_schema=databento_request.schema,
            timeframe=resolved_timeframe,
            start=databento_request.start,
            end=databento_request.end,
            session_date=databento_request.start.date(),
            mode=normalized_mode,
            allow_live_databento_request=allow_live,
            stype_in=databento_request.stype_in,
            limit=databento_request.limit,
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> MarketDataRequestConfig:
        """Load a request plan from environment-style values."""

        source = {} if env is None else env
        return cls.create(
            symbol=source.get("MARKET_DATA_SYMBOL", DEFAULT_SPY_SMOKE_REQUEST["symbol"]),
            vendor=source.get("MARKET_DATA_VENDOR", DEFAULT_MARKET_DATA_VENDOR),
            dataset=source.get("MARKET_DATA_DATASET", DEFAULT_DATABENTO_DATASET),
            source_schema=source.get("MARKET_DATA_SOURCE_SCHEMA", DEFAULT_DATABENTO_SCHEMA),
            timeframe=source.get("MARKET_DATA_TIMEFRAME", DEFAULT_MARKET_DATA_TIMEFRAME),
            start=source.get("MARKET_DATA_START", DEFAULT_SPY_SMOKE_REQUEST["start"]),
            end=source.get("MARKET_DATA_END", DEFAULT_SPY_SMOKE_REQUEST["end"]),
            mode=source.get("MARKET_DATA_MODE", EXISTING_SAMPLE_MODE),
            allow_live_databento_request=source.get(ALLOW_LIVE_DATABENTO_ENV_VAR, "false"),
            stype_in=source.get("MARKET_DATA_STYPE_IN", DEFAULT_DATABENTO_STYPE_IN),
            limit=source.get("MARKET_DATA_LIMIT", str(DEFAULT_DATABENTO_LIMIT)),
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> MarketDataRequestConfig:
        """Rebuild a validated request plan from asset output metadata."""

        return cls.create(
            symbol=str(values.get("symbol", DEFAULT_SPY_SMOKE_REQUEST["symbol"])),
            vendor=str(values.get("vendor", DEFAULT_MARKET_DATA_VENDOR)),
            dataset=str(values.get("dataset", DEFAULT_DATABENTO_DATASET)),
            source_schema=str(values.get("source_schema", DEFAULT_DATABENTO_SCHEMA)),
            timeframe=str(values.get("timeframe", DEFAULT_MARKET_DATA_TIMEFRAME)),
            start=str(values.get("start", DEFAULT_SPY_SMOKE_REQUEST["start"])),
            end=str(values.get("end", DEFAULT_SPY_SMOKE_REQUEST["end"])),
            mode=str(values.get("mode", EXISTING_SAMPLE_MODE)),
            allow_live_databento_request=values.get("allow_live_databento_request", "false"),
            stype_in=str(values.get("stype_in", DEFAULT_DATABENTO_STYPE_IN)),
            limit=values.get("limit", DEFAULT_DATABENTO_LIMIT),
        )

    @property
    def uses_live_databento(self) -> bool:
        """Return whether the request plan will call Databento."""

        return self.mode == LIVE_DATABENTO_MODE

    def to_databento_request(self) -> DatabentoSmokeRequest:
        """Convert to the existing guarded Databento request shape."""

        return DatabentoSmokeRequest.create(
            symbol=self.symbol,
            start=self.start,
            end=self.end,
            dataset=self.dataset,
            schema=self.source_schema,
            stype_in=self.stype_in,
            limit=self.limit,
        )

    def to_metadata(self) -> dict[str, str]:
        """Return safe, loggable metadata for Dagster and scripts."""

        return {
            "symbol": self.symbol,
            "vendor": self.vendor,
            "dataset": self.dataset,
            "source_schema": self.source_schema,
            "timeframe": self.timeframe,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "session_date": self.session_date.isoformat(),
            "mode": self.mode,
            "allow_live_databento_request": str(self.allow_live_databento_request).lower(),
            "live_databento_used": str(self.uses_live_databento).lower(),
            "stype_in": self.stype_in,
            "limit": str(self.limit),
        }


def parse_bool(value: bool | str | object) -> bool:
    """Parse bool-ish configuration values."""

    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_mode(mode: str) -> str:
    normalized = _normalize_non_empty("mode", mode).lower()
    if normalized not in {EXISTING_SAMPLE_MODE, LIVE_DATABENTO_MODE}:
        raise MarketDataRequestConfigError(
            f"Market-data mode must be {EXISTING_SAMPLE_MODE} or {LIVE_DATABENTO_MODE}."
        )
    return normalized


def _normalize_non_empty(field_name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise MarketDataRequestConfigError(f"Market-data {field_name} must not be empty.")
    return normalized


def _parse_int(field_name: str, value: int | str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataRequestConfigError(f"Market-data {field_name} must be an integer.") from exc
