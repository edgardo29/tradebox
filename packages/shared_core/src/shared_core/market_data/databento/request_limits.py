"""Credit-preserving request limits for manual Databento smoke tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.storage.object_keys import build_object_key

DATABENTO_SMOKE_RAW_PREFIX = "dev/databento-smoke-tests/raw/"
DEFAULT_DATABENTO_DATASET = "EQUS.MINI"
DEFAULT_DATABENTO_SCHEMA = "ohlcv-1m"
DEFAULT_DATABENTO_STYPE_IN = "raw_symbol"
DEFAULT_DATABENTO_LIMIT = 1
MAX_SMOKE_WINDOW = timedelta(minutes=5)
MAX_SMOKE_RECORD_LIMIT = 10
DEFAULT_SPY_SMOKE_REQUEST = {
    "symbol": "SPY",
    "dataset": DEFAULT_DATABENTO_DATASET,
    "schema": DEFAULT_DATABENTO_SCHEMA,
    "start": "2024-01-02T14:30:00Z",
    "end": "2024-01-02T14:31:00Z",
    "limit": DEFAULT_DATABENTO_LIMIT,
}


class DatabentoSmokeRequestError(ValueError):
    """Raised when a Databento smoke request can spend too many credits."""


@dataclass(frozen=True)
class DatabentoSmokeRequest:
    """Validated tiny historical request for a manual Databento smoke test."""

    symbol: str
    start: datetime
    end: datetime
    dataset: str = DEFAULT_DATABENTO_DATASET
    schema: str = DEFAULT_DATABENTO_SCHEMA
    stype_in: str = DEFAULT_DATABENTO_STYPE_IN
    limit: int = DEFAULT_DATABENTO_LIMIT

    @classmethod
    def create(
        cls,
        *,
        symbol: str = DEFAULT_SPY_SMOKE_REQUEST["symbol"],
        start: str | datetime = DEFAULT_SPY_SMOKE_REQUEST["start"],
        end: str | datetime = DEFAULT_SPY_SMOKE_REQUEST["end"],
        dataset: str = DEFAULT_DATABENTO_DATASET,
        schema: str = DEFAULT_DATABENTO_SCHEMA,
        stype_in: str = DEFAULT_DATABENTO_STYPE_IN,
        limit: int = DEFAULT_DATABENTO_LIMIT,
    ) -> DatabentoSmokeRequest:
        request = cls(
            symbol=normalize_single_symbol(symbol),
            dataset=_normalize_non_empty("dataset", dataset),
            schema=_normalize_non_empty("schema", schema),
            stype_in=_normalize_non_empty("stype_in", stype_in),
            start=_parse_datetime("start", start),
            end=_parse_datetime("end", end),
            limit=limit,
        )
        request.validate()
        return request

    @property
    def session_date(self) -> str:
        return self.start.date().isoformat()

    @property
    def raw_file_format(self) -> str:
        return "dbn.zst"

    @property
    def timeframe(self) -> str:
        if self.schema == "ohlcv-1m":
            return "1m"
        if self.schema == "ohlcv-5m":
            return "5m"
        return "1m"

    def validate(self) -> None:
        if self.end <= self.start:
            raise DatabentoSmokeRequestError("Databento smoke end must be after start.")
        if self.end - self.start > MAX_SMOKE_WINDOW:
            raise DatabentoSmokeRequestError(
                "Databento smoke request window is too broad. "
                f"Use {int(MAX_SMOKE_WINDOW.total_seconds() // 60)} minutes or less."
            )
        if self.limit <= 0 or self.limit > MAX_SMOKE_RECORD_LIMIT:
            raise DatabentoSmokeRequestError(
                f"Databento smoke record limit must be between 1 and {MAX_SMOKE_RECORD_LIMIT}."
            )
        if self.symbol == "ALL_SYMBOLS":
            raise DatabentoSmokeRequestError("Databento smoke tests must request one symbol only.")


def normalize_single_symbol(symbol: str) -> str:
    """Normalize and validate a single raw symbol."""
    if not isinstance(symbol, str):
        raise DatabentoSmokeRequestError("Databento smoke symbol must be a string.")

    normalized = symbol.strip().upper()
    if not normalized:
        raise DatabentoSmokeRequestError("Databento smoke symbol must not be empty.")
    if any(separator in normalized for separator in [",", ";", "|"]):
        raise DatabentoSmokeRequestError("Databento smoke tests do not allow symbol lists.")
    if any(character.isspace() for character in normalized):
        raise DatabentoSmokeRequestError("Databento smoke tests do not allow symbol lists.")
    return normalized


def databento_smoke_raw_object_key(request: DatabentoSmokeRequest, run_id: UUID) -> str:
    """Build the private R2 object key for a raw Databento smoke sample."""
    filename = f"{run_id.hex}.{request.raw_file_format}"
    return build_object_key(
        DATABENTO_SMOKE_RAW_PREFIX,
        request.dataset,
        request.symbol,
        request.schema,
        request.session_date,
        filename,
    )


def _parse_datetime(field_name: str, value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise DatabentoSmokeRequestError(f"Databento smoke {field_name} must be a datetime.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_non_empty(field_name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DatabentoSmokeRequestError(f"Databento smoke {field_name} must not be empty.")
    return normalized
