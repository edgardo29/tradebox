"""Convert an existing raw Databento smoke sample to clean Parquet in R2."""

from __future__ import annotations

import argparse
import sys

from shared_core.storage import R2ConfigError
from tradebox_workflows import load_local_env_file, print_metadata, raw_databento_partition_to_clean


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert an existing raw Databento OHLCV sample to clean Parquet."
    )
    parser.add_argument("--symbol", default="SPY")
    args = parser.parse_args()

    load_local_env_file()

    try:
        result = raw_databento_partition_to_clean(symbol=args.symbol)
        print("Raw-to-clean smoke conversion succeeded.")
        print_metadata(result)
        return 0
    except R2ConfigError as exc:
        print(f"R2 configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Raw-to-clean SPY smoke conversion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
