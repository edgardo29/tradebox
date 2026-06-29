"""Run a tiny Databento SPY historical smoke ingestion into private R2 and Postgres."""

from __future__ import annotations

import argparse
import sys

from shared_core.market_data.databento import (
    DEFAULT_SPY_SMOKE_REQUEST,
    DatabentoConfigError,
    DatabentoSmokeRequest,
    DatabentoSmokeRequestError,
)
from shared_core.storage import R2ConfigError
from tradebox_workflows import ingest_databento_smoke_partition, load_local_env_file, print_metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch one tiny Databento historical SPY sample, upload raw DBN to R2, "
            "and catalog it in data_partitions."
        )
    )
    parser.add_argument("--symbol", default=DEFAULT_SPY_SMOKE_REQUEST["symbol"])
    parser.add_argument("--start", default=DEFAULT_SPY_SMOKE_REQUEST["start"])
    parser.add_argument("--end", default=DEFAULT_SPY_SMOKE_REQUEST["end"])
    parser.add_argument("--dataset", default=DEFAULT_SPY_SMOKE_REQUEST["dataset"])
    parser.add_argument("--schema", default=DEFAULT_SPY_SMOKE_REQUEST["schema"])
    parser.add_argument("--limit", type=int, default=DEFAULT_SPY_SMOKE_REQUEST["limit"])
    parser.add_argument(
        "--confirm-credit-use",
        action="store_true",
        help="Required. Confirms this live smoke command may consume Databento credits.",
    )
    args = parser.parse_args()

    if not args.confirm_credit_use:
        print(
            "Refusing to run live Databento smoke without --confirm-credit-use. "
            "This command may consume Databento credits.",
            file=sys.stderr,
        )
        return 2

    print("Warning: this live Databento smoke request may consume Databento credits.")
    load_local_env_file()

    try:
        request = DatabentoSmokeRequest.create(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            dataset=args.dataset,
            schema=args.schema,
            limit=args.limit,
        )
        result = ingest_databento_smoke_partition(
            request,
            confirm_credit_use=args.confirm_credit_use,
        )
        print("Databento SPY smoke ingestion succeeded.")
        print_metadata(result)
        return 0
    except (DatabentoConfigError, R2ConfigError, DatabentoSmokeRequestError, RuntimeError) as exc:
        print(f"Databento SPY smoke ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
