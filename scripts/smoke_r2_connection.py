"""Run a live Cloudflare R2 smoke test against the private dev bucket."""

from __future__ import annotations

import sys

from shared_core.storage.r2_client import run_r2_smoke_test
from shared_core.storage.r2_config import R2ConfigError, load_r2_config_from_env


def _load_local_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def main() -> int:
    _load_local_env_file()

    try:
        config = load_r2_config_from_env()
    except R2ConfigError as exc:
        print(f"R2 configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        result = run_r2_smoke_test(config)
    except Exception as exc:
        print(f"R2 smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("R2 smoke test succeeded.")
    print(f"bucket={result.bucket_name}")
    print(f"object_key={result.object_key}")
    print("The smoke-test object was deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
