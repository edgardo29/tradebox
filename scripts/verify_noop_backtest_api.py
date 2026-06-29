"""Verify backend API metadata for the latest no-op SPY backtest run."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, Instrument
from app.db.session import SessionLocal
from app.main import app


def _load_local_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def main() -> int:
    _load_local_env_file()

    session = SessionLocal()
    try:
        run = _load_latest_noop_spy_backtest(session)
        client = TestClient(app)

        by_id_response = client.get(f"/backtest-runs/{run.id}")
        by_id_response.raise_for_status()
        by_id = by_id_response.json()

        list_response = client.get(
            "/backtest-runs",
            params={
                "symbol": "SPY",
                "run_status": "succeeded",
                "strategy_name": "noop_smoke",
                "timeframe": "1m",
            },
        )
        list_response.raise_for_status()
        matching = [row for row in list_response.json() if row["id"] == str(run.id)]
        if len(matching) != 1:
            raise RuntimeError("No-op SPY backtest was not found exactly once in API list.")

        _assert_completed_metadata(by_id)

        print("No-op SPY backtest API verification succeeded.")
        print(f"backtest_run_id={by_id['id']}")
        print(f"instrument_symbol={by_id['instrument_symbol']}")
        print(f"run_status={by_id['run_status']}")
        print(f"strategy_name={by_id['strategy_name']}")
        print(f"strategy_version={by_id['strategy_version']}")
        print(f"candle_count={by_id['metrics_json']['candle_count']}")
        print(f"detected_setup_count={by_id['metrics_json']['detected_setup_count']}")
        print(f"simulated_trade_count={by_id['metrics_json']['simulated_trade_count']}")
        return 0
    except Exception as exc:
        print(f"No-op SPY backtest API verification failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


def _load_latest_noop_spy_backtest(session: Session) -> BacktestRun:
    statement = (
        select(BacktestRun)
        .join(Instrument, BacktestRun.instrument_id == Instrument.id)
        .where(
            Instrument.symbol == "SPY",
            BacktestRun.strategy_name == "noop_smoke",
            BacktestRun.run_status == "succeeded",
        )
        .order_by(BacktestRun.updated_at.desc())
    )
    run = session.scalars(statement).first()
    if run is None:
        raise RuntimeError("No succeeded noop_smoke SPY backtest run was found.")
    return run


def _assert_completed_metadata(row: dict[str, object]) -> None:
    required_values = [
        "id",
        "instrument_id",
        "instrument_symbol",
        "run_status",
        "strategy_name",
        "strategy_version",
        "strategy_config_hash",
        "timeframe",
        "start_date",
        "end_date",
        "parameters_json",
        "input_data_snapshot_json",
        "metrics_json",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ]
    missing = [
        field
        for field in required_values
        if row.get(field) is None or row.get(field) == ""
    ]
    if missing:
        raise RuntimeError(f"No-op backtest API response is missing: {missing}")

    serialized = str(row).lower()
    forbidden_tokens = ["access_key", "secret_access_key", "databento_api_key"]
    leaked = [token for token in forbidden_tokens if token in serialized]
    if leaked:
        raise RuntimeError(f"API response includes secret-looking tokens: {leaked}")


if __name__ == "__main__":
    raise SystemExit(main())
