"""Clean market-data schema types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CleanOhlcvBar:
    """Clean 1-minute OHLCV bar."""

    symbol: str
    ts_event: datetime
    session_date: date
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source_vendor: str
    source_dataset: str
    source_schema: str
    processed_at: datetime

    def to_mapping(self) -> dict[str, object]:
        """Return a serializable mapping for table/parquet writers."""
        return asdict(self)
