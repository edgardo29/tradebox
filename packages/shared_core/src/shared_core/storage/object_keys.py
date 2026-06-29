"""Object key helpers for private object storage."""

from __future__ import annotations

DEV_SMOKE_TEST_PREFIX = "dev/smoke-tests/"
CLEAN_OHLCV_FILENAME = "part-000.parquet"
RAW_MARKET_DATA_PREFIX = "raw"


def ensure_key_prefix(prefix: str) -> str:
    """Normalize a storage prefix and ensure it ends with a slash."""
    normalized = _normalize_key_part(prefix, allow_slashes=True)
    return f"{normalized}/"


def build_object_key(*parts: str) -> str:
    """Build a normalized object key from path-like parts."""
    if not parts:
        raise ValueError("Object key requires at least one part.")

    normalized_parts = [_normalize_key_part(part, allow_slashes=True) for part in parts]
    return "/".join(normalized_parts)


def smoke_test_object_key(object_name: str) -> str:
    """Build the key used by the R2 live smoke test."""
    return build_object_key(DEV_SMOKE_TEST_PREFIX, object_name)


def clean_ohlcv_object_key(
    *,
    vendor: str,
    dataset: str,
    symbol: str,
    timeframe: str,
    session_date: str,
    filename: str = CLEAN_OHLCV_FILENAME,
) -> str:
    """Build the clean OHLCV Parquet object key."""
    return build_object_key(
        "clean",
        f"vendor={vendor}",
        f"dataset={dataset}",
        f"symbol={symbol}",
        f"timeframe={timeframe}",
        f"session_date={session_date}",
        filename,
    )


def raw_market_data_object_key(
    *,
    vendor: str,
    dataset: str,
    symbol: str,
    source_schema: str,
    session_date: str,
    run_id: str,
    file_extension: str = "dbn.zst",
) -> str:
    """Build the raw market-data object key for future controlled ingestion."""
    return build_object_key(
        RAW_MARKET_DATA_PREFIX,
        f"vendor={vendor}",
        f"dataset={dataset}",
        f"symbol={symbol}",
        f"schema={source_schema}",
        f"session_date={session_date}",
        f"{run_id}.{file_extension}",
    )


def market_data_partition_key(
    *,
    vendor: str,
    dataset: str,
    symbol: str,
    timeframe: str,
    session_date: str,
) -> str:
    """Build a stable logical partition identity string."""
    return "|".join(
        [
            f"vendor={vendor}",
            f"dataset={dataset}",
            f"symbol={symbol}",
            f"timeframe={timeframe}",
            f"session_date={session_date}",
        ]
    )


def _normalize_key_part(part: str, *, allow_slashes: bool) -> str:
    normalized = part.strip().strip("/")
    if not normalized:
        raise ValueError("Object key parts must not be empty.")
    if "\\" in normalized:
        raise ValueError("Object key parts must use forward slashes.")
    if "//" in normalized:
        raise ValueError("Object key parts must not contain empty path segments.")

    segments = normalized.split("/") if allow_slashes else [normalized]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("Object key parts must not contain relative path segments.")

    return normalized
