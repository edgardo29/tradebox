"""Shared storage helpers."""

from shared_core.storage.content_hash import sha256_bytes, sha256_file, sha256_text
from shared_core.storage.object_keys import (
    CLEAN_OHLCV_FILENAME,
    DEV_SMOKE_TEST_PREFIX,
    RAW_MARKET_DATA_PREFIX,
    build_object_key,
    clean_ohlcv_object_key,
    ensure_key_prefix,
    market_data_partition_key,
    raw_market_data_object_key,
    smoke_test_object_key,
)
from shared_core.storage.r2_config import R2Config, R2ConfigError, load_r2_config_from_env

__all__ = [
    "DEV_SMOKE_TEST_PREFIX",
    "CLEAN_OHLCV_FILENAME",
    "RAW_MARKET_DATA_PREFIX",
    "R2Config",
    "R2ConfigError",
    "build_object_key",
    "clean_ohlcv_object_key",
    "ensure_key_prefix",
    "load_r2_config_from_env",
    "market_data_partition_key",
    "raw_market_data_object_key",
    "sha256_bytes",
    "sha256_file",
    "sha256_text",
    "smoke_test_object_key",
]
