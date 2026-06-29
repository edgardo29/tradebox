"""Backtesting workflow functions shared by scripts and future pipeline assets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from app.db.models import BacktestRun, DataPartition, Instrument
from app.db.session import SessionLocal
from app.services.backtest_runs import (
    build_backtest_input_snapshot,
    create_backtest_run_from_config,
    mark_backtest_run_failed,
    mark_backtest_run_running,
    mark_backtest_run_succeeded,
    write_backtest_results,
)
from shared_core.backtesting import BacktestConfig, BacktestRunner, load_clean_ohlcv_parquet_bytes
from shared_core.storage import load_r2_config_from_env
from shared_core.storage.r2_client import R2StorageClient
from sqlalchemy import select
from sqlalchemy.orm import Session

SessionFactory = Callable[[], Session]


def run_noop_backtest(
    *,
    symbol: str = "SPY",
    session_factory: SessionFactory = SessionLocal,
    r2_client: R2StorageClient | None = None,
) -> dict[str, object]:
    """Run a no-op backtest against the latest clean partition for a symbol."""

    r2_client = r2_client or R2StorageClient(load_r2_config_from_env())
    session = session_factory()
    run: BacktestRun | None = None
    try:
        partition, instrument = load_latest_clean_partition(session, symbol=symbol)
        if partition.clean_object_path is None:
            raise RuntimeError(f"Latest {symbol} partition has no clean_object_path.")

        clean_bytes = r2_client.read_bytes(partition.clean_object_path)
        candles = load_clean_ohlcv_parquet_bytes(clean_bytes)
        if not candles:
            raise RuntimeError(f"Clean {symbol} partition loaded zero candles.")

        start = candles[0].ts_event
        end = candles[-1].ts_event + timedelta(minutes=1)
        config = BacktestConfig.create(
            symbol=instrument.symbol,
            timeframe=partition.timeframe,
            start=start,
            end=end,
            clean_data_partition_id=partition.id,
            strategy_name="noop_smoke",
            strategy_version="0.1.0",
            metadata={"source": "tradebox_workflows.backtesting.run_noop_backtest"},
        )
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=build_backtest_input_snapshot(partition),
            execution_assumptions={"strategy": "placeholder_noop", "fills": "none"},
            commit=True,
        )
        mark_backtest_run_running(session, run, commit=True)

        result = BacktestRunner().run(config=config, candles=candles)
        write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result, commit=True)

        return {
            "backtest_run_id": run.id,
            "instrument_symbol": instrument.symbol,
            "data_partition_id": partition.id,
            "clean_object_path": partition.clean_object_path,
            "run_status": run.run_status,
            "strategy_name": run.strategy_name,
            "strategy_version": run.strategy_version,
            "candle_count": run.metrics_json.get("candle_count"),
            "detected_setup_count": run.metrics_json.get("detected_setup_count"),
            "simulated_trade_count": run.metrics_json.get("simulated_trade_count"),
        }
    except Exception as exc:
        session.rollback()
        if run is not None:
            try:
                mark_backtest_run_failed(session, run, error_message=str(exc), commit=True)
            except Exception:
                session.rollback()
        raise
    finally:
        session.close()


def load_latest_clean_partition(
    session: Session,
    *,
    symbol: str,
) -> tuple[DataPartition, Instrument]:
    """Load the latest validated clean Databento partition for a symbol."""

    statement = (
        select(DataPartition, Instrument)
        .join(Instrument, DataPartition.instrument_id == Instrument.id)
        .where(
            Instrument.symbol == symbol.strip().upper(),
            DataPartition.vendor == "databento",
            DataPartition.clean_object_path.is_not(None),
            DataPartition.partition_status == "validated",
            DataPartition.clean_file_format == "parquet",
        )
        .order_by(DataPartition.updated_at.desc())
    )
    row = session.execute(statement).first()
    if row is None:
        raise RuntimeError(f"No validated clean {symbol} data_partitions row was found.")
    return row
