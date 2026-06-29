"""Small Databento historical client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from shared_core.config.databento_config import DatabentoConfig
from shared_core.market_data.databento.request_limits import DatabentoSmokeRequest
from shared_core.storage import sha256_bytes


@dataclass(frozen=True)
class DatabentoRawSample:
    """Raw Databento sample bytes and metadata."""

    content: bytes
    content_hash: str
    record_count: int | None
    raw_file_format: str


class DatabentoHistoricalClient:
    """Minimal historical client wrapper for tiny manual smoke requests."""

    def __init__(self, config: DatabentoConfig, historical_client: object | None = None) -> None:
        self.config = config
        self._client = (
            historical_client if historical_client is not None else _build_historical_client(config)
        )

    def get_raw_sample(self, request: DatabentoSmokeRequest) -> DatabentoRawSample:
        """Fetch a tiny historical sample and return compressed DBN bytes."""
        with TemporaryDirectory(prefix="tradebox-databento-smoke-") as temp_dir:
            filename = f"{request.symbol.lower()}-sample.{request.raw_file_format}"
            output_path = Path(temp_dir) / filename
            data = self._client.timeseries.get_range(
                dataset=request.dataset,
                symbols=request.symbol,
                schema=request.schema,
                start=request.start.isoformat(),
                end=request.end.isoformat(),
                stype_in=request.stype_in,
                limit=request.limit,
            )
            record_count = _count_records(data, request)
            data.to_file(output_path)
            content = output_path.read_bytes()

        if not content:
            raise RuntimeError("Databento returned an empty raw sample.")

        return DatabentoRawSample(
            content=content,
            content_hash=sha256_bytes(content),
            record_count=record_count,
            raw_file_format=request.raw_file_format,
        )


def _build_historical_client(config: DatabentoConfig) -> object:
    try:
        import databento as db
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "databento is required for Databento smoke ingestion. "
            "Install the shared_core package dependencies."
        ) from exc

    return db.Historical(config.api_key)


def _count_records(data: object, request: DatabentoSmokeRequest) -> int | None:
    try:
        records = data.to_ndarray(schema=request.schema)
    except Exception:
        return None
    try:
        return len(records)
    except TypeError:
        return None
