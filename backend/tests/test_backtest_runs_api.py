from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from shared_core.backtesting import (
    BacktestCandle,
    BacktestConfig,
    BacktestRunner,
    BacktestRunResult,
)
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, DataPartition, DetectedSetup, Instrument, SimulatedTrade
from app.db.session import SessionLocal
from app.main import app
from app.schemas.data_partition import DataPartitionCreate
from app.services.backtest_runs import (
    BacktestInputPartitionError,
    BacktestResultPersistenceError,
    build_backtest_input_snapshot,
    create_backtest_run_from_config,
    mark_backtest_run_failed,
    mark_backtest_run_running,
    mark_backtest_run_succeeded,
    write_backtest_results,
)
from app.services.data_partitions import upsert_data_partition


def test_backtest_run_lifecycle_succeeds_with_zero_results() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBT1")
        config = _config(partition.id)
        snapshot = build_backtest_input_snapshot(partition)

        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=snapshot,
        )
        assert run.run_status == "pending"
        assert run.parameters_json["strategy_name"] == "noop_test"
        assert run.input_data_snapshot_json["clean_object_path"] == partition.clean_object_path

        mark_backtest_run_running(session, run)
        assert run.run_status == "running"
        assert run.started_at is not None

        result = BacktestRunner().run(config=config, candles=[_candle()])
        counts = write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result)
        session.commit()
        session.refresh(run)

        assert counts == {"detected_setup_count": 0, "simulated_trade_count": 0}
        assert run.run_status == "succeeded"
        assert run.finished_at is not None
        assert run.error_message is None
        assert run.metrics_json["candle_count"] == 1
        assert run.metrics_json["detected_setup_count"] == 0
        assert run.metrics_json["simulated_trade_count"] == 0


def test_backtest_run_lifecycle_persists_setups_and_trades() -> None:
    client = TestClient(app)
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTSETUP")
        config = _config(partition.id)
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )
        mark_backtest_run_running(session, run)

        result = BacktestRunResult(
            run_status="succeeded",
            strategy_name="fixture_strategy",
            strategy_version="0.1.0",
            candle_count=3,
            detected_setups=[
                {
                    "setup_key": "TBXBTSETUP-2024-01-02T14:30:00Z-long",
                    "setup_status": "triggered",
                    "side": "long",
                    "detected_at": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                    "setup_start_at": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                    "setup_end_at": datetime(2024, 1, 2, 14, 32, tzinfo=UTC),
                    "triggered_at": datetime(2024, 1, 2, 14, 33, tzinfo=UTC),
                    "entry_price": "100.50",
                    "stop_price": "99.90",
                    "target_price": "101.70",
                    "metadata": {"pattern": "two_legged_pullback"},
                }
            ],
            simulated_trades=[
                {
                    "trade_key": "TBXBTSETUP-trade-1",
                    "detected_setup_key": "TBXBTSETUP-2024-01-02T14:30:00Z-long",
                    "trade_status": "closed",
                    "side": "long",
                    "entry_at": datetime(2024, 1, 2, 14, 33, tzinfo=UTC),
                    "entry_price": "100.50",
                    "exit_at": datetime(2024, 1, 2, 14, 39, tzinfo=UTC),
                    "exit_price": "101.70",
                    "quantity": "10",
                    "risk_amount": "6.00",
                    "gross_pnl": "12.00",
                    "net_pnl": "11.50",
                    "fees": "0.50",
                    "r_multiple": "2.0",
                    "exit_reason": "target_hit",
                    "metadata": {"fill_model": "next_bar_limit"},
                }
            ],
            metrics={"fixture_metric": 42},
        )

        counts = write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result)
        session.commit()
        session.refresh(run)

        setup = session.query(DetectedSetup).filter_by(backtest_run_id=run.id).one()
        trade = session.query(SimulatedTrade).filter_by(backtest_run_id=run.id).one()
        run_id = run.id
        metrics = dict(run.metrics_json)
        setup_id = setup.id
        setup_metadata = dict(setup.setup_metadata_json)
        trade_detected_setup_id = trade.detected_setup_id
        trade_metadata = dict(trade.trade_metadata_json)

        setup_response = client.get(f"/backtest-runs/{run_id}/detected-setups")
        trade_response = client.get(f"/backtest-runs/{run_id}/simulated-trades")

    assert counts == {"detected_setup_count": 1, "simulated_trade_count": 1}
    assert metrics["fixture_metric"] == 42
    assert metrics["detected_setup_count"] == 1
    assert metrics["simulated_trade_count"] == 1
    assert setup_metadata == {"pattern": "two_legged_pullback"}
    assert trade_detected_setup_id == setup_id
    assert trade_metadata == {"fill_model": "next_bar_limit"}

    assert setup_response.status_code == 200
    setup_body = setup_response.json()
    assert len(setup_body) == 1
    assert setup_body[0]["setup_key"] == "TBXBTSETUP-2024-01-02T14:30:00Z-long"
    assert setup_body[0]["setup_status"] == "triggered"
    assert setup_body[0]["setup_metadata_json"] == {"pattern": "two_legged_pullback"}

    assert trade_response.status_code == 200
    trade_body = trade_response.json()
    assert len(trade_body) == 1
    assert trade_body[0]["trade_key"] == "TBXBTSETUP-trade-1"
    assert trade_body[0]["detected_setup_id"] == str(setup_id)
    assert trade_body[0]["trade_metadata_json"] == {"fill_model": "next_bar_limit"}


def test_backtest_result_persistence_validates_required_fields() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTBAD")
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=_config(partition.id),
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )
        result = BacktestRunResult(
            run_status="succeeded",
            strategy_name="fixture_strategy",
            strategy_version="0.1.0",
            candle_count=1,
            detected_setups=[],
            simulated_trades=[
                {
                    "trade_key": "missing-entry-price",
                    "side": "long",
                    "entry_at": datetime(2024, 1, 2, 14, 33, tzinfo=UTC),
                }
            ],
            metrics={},
        )

        try:
            write_backtest_results(session, run, result)
        except BacktestResultPersistenceError as exc:
            assert "entry_price" in str(exc)
        else:
            raise AssertionError("Expected BacktestResultPersistenceError.")


def test_backtest_run_lifecycle_marks_failure() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBT2")
        config = _config(partition.id)
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )

        mark_backtest_run_running(session, run)
        mark_backtest_run_failed(session, run, error_message="fixture failure")
        session.commit()
        session.refresh(run)

        assert run.run_status == "failed"
        assert run.error_message == "fixture failure"
        assert run.finished_at is not None


def test_backtest_input_snapshot_requires_clean_object_path() -> None:
    with _db_session() as session:
        _, partition = _create_instrument_and_partition(
            session,
            symbol="TBXBT3",
            clean_object_path=None,
        )

        try:
            build_backtest_input_snapshot(partition)
        except BacktestInputPartitionError as exc:
            assert "clean_object_path" in str(exc)
        else:
            raise AssertionError("Expected BacktestInputPartitionError.")


def test_backtest_input_snapshot_requires_clean_or_validated_partition() -> None:
    with _db_session() as session:
        _, partition = _create_instrument_and_partition(
            session,
            symbol="TBXBT4",
            partition_status="raw_available",
        )

        try:
            build_backtest_input_snapshot(partition)
        except BacktestInputPartitionError as exc:
            assert "clean or validated" in str(exc)
        else:
            raise AssertionError("Expected BacktestInputPartitionError.")


def test_backtest_runs_api_lists_and_gets_metadata() -> None:
    client = TestClient(app)
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBT5")
        config = _config(partition.id)
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )
        result = BacktestRunner().run(config=config, candles=[_candle()])
        write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result)
        session.commit()
        session.refresh(run)
        run_id = run.id

        get_response = client.get(f"/backtest-runs/{run_id}")
        list_response = client.get(
            "/backtest-runs",
            params={
                "symbol": "tbxbt5",
                "run_status": "succeeded",
                "strategy_name": "noop_test",
                "timeframe": "1m",
            },
        )

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == str(run_id)
    assert body["instrument_symbol"] == "TBXBT5"
    assert body["run_status"] == "succeeded"
    assert body["metrics_json"]["simulated_trade_count"] == 0
    assert "secret" not in str(body).lower()

    assert list_response.status_code == 200
    assert str(run_id) in {row["id"] for row in list_response.json()}


def test_backtest_run_api_returns_404_for_missing_id() -> None:
    response = TestClient(app).get(f"/backtest-runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Backtest run not found."}


def test_backtest_result_detail_api_returns_404_for_missing_run() -> None:
    missing_id = uuid.uuid4()

    setup_response = TestClient(app).get(f"/backtest-runs/{missing_id}/detected-setups")
    trade_response = TestClient(app).get(f"/backtest-runs/{missing_id}/simulated-trades")

    assert setup_response.status_code == 404
    assert setup_response.json() == {"detail": "Backtest run not found."}
    assert trade_response.status_code == 404
    assert trade_response.json() == {"detail": "Backtest run not found."}


@contextmanager
def _db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            delete(SimulatedTrade).where(SimulatedTrade.trade_key.like("TBXBT%"))
        )
        session.execute(
            delete(DetectedSetup).where(DetectedSetup.setup_key.like("TBXBT%"))
        )
        session.execute(delete(BacktestRun).where(BacktestRun.strategy_name == "noop_test"))
        session.execute(delete(BacktestRun).where(BacktestRun.strategy_name == "fixture_strategy"))
        session.execute(
            delete(DataPartition).where(
                DataPartition.vendor == "test",
                DataPartition.dataset == "backtest_api_test",
            )
        )
        session.execute(delete(Instrument).where(Instrument.symbol.like("TBXBT%")))
        session.commit()
        session.close()


def _create_instrument_and_partition(
    session: Session,
    *,
    symbol: str,
    clean_object_path: str | None = (
        "clean/vendor=test/dataset=backtest_api_test/symbol=SPY/timeframe=1m/"
        "session_date=2024-01-02/part-000.parquet"
    ),
    partition_status: str = "validated",
) -> tuple[Instrument, DataPartition]:
    instrument = Instrument(
        symbol=symbol,
        name=f"{symbol} Backtest Fixture",
        asset_class="equity",
        exchange="TEST",
    )
    session.add(instrument)
    session.flush()

    partition = upsert_data_partition(
        session,
        DataPartitionCreate(
            instrument_id=instrument.id,
            vendor="test",
            dataset="backtest_api_test",
            timeframe="1m",
            session_date=date(2024, 1, 2),
            raw_object_path="raw/test.dbn.zst",
            clean_object_path=clean_object_path,
            raw_file_format="dbn.zst",
            clean_file_format="parquet",
            partition_status=partition_status,
            row_count=1,
            validation_error_count=0,
            schema_version="1",
            raw_content_hash="raw123",
            clean_content_hash="clean123" if clean_object_path else None,
        ),
    )
    session.flush()
    return instrument, partition


def _config(partition_id: uuid.UUID) -> BacktestConfig:
    return BacktestConfig.create(
        symbol="SPY",
        timeframe="1m",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        clean_data_partition_id=partition_id,
        strategy_name="noop_test",
    )


def _candle() -> BacktestCandle:
    return BacktestCandle(
        symbol="SPY",
        ts_event=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        session_date=date(2024, 1, 2),
        timeframe="1m",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000,
    )
