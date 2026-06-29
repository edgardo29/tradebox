"""Describe the latest existing raw market-data partition from local Postgres."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from tradebox_workflows import (
    describe_existing_raw_market_data_partition,
    load_local_env_file,
    print_metadata,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Describe an existing raw market-data partition without reading R2 objects."
    )
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--vendor", default="databento")
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--session-date", default=None)
    args = parser.parse_args()

    load_local_env_file()

    try:
        result = describe_existing_raw_market_data_partition(
            symbol=args.symbol,
            vendor=args.vendor,
            timeframe=args.timeframe,
            dataset=args.dataset,
            session_date=_parse_session_date(args.session_date),
        )
        print("Existing market-data raw partition located.")
        print_metadata(result)
        return 0
    except Exception as exc:
        print(f"Existing market-data raw partition lookup failed: {exc}", file=sys.stderr)
        return 1


def _parse_session_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
