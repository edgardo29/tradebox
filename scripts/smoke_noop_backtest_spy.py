"""Run a tiny no-op backtest using the existing clean SPY partition."""

from __future__ import annotations

import argparse
import sys

from shared_core.storage import R2ConfigError
from tradebox_workflows import load_local_env_file, print_metadata, run_noop_backtest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a no-op backtest using the latest clean symbol partition."
    )
    parser.add_argument("--symbol", default="SPY")
    args = parser.parse_args()

    load_local_env_file()

    try:
        result = run_noop_backtest(symbol=args.symbol)
        print("No-op SPY backtest smoke succeeded.")
        print_metadata(result)
        return 0
    except R2ConfigError as exc:
        print(f"R2 configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"No-op SPY backtest smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
