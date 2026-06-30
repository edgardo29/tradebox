from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from shared_core.backtesting import (
    BacktestCandle,
    BacktestConfig,
    BacktestRunner,
    BacktestRunResult,
)
from shared_core.strategy.two_legged_pullback import TwoLeggedPullbackStrategy
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
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
        assert run.parameters_json["strategy_name"] == "noop"
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


def test_backtest_result_persistence_accepts_v1_strategy_values() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTV1")
        instrument_id = str(instrument.id)
        skipped_trade_date = "2024-01-03"
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=_config(partition.id),
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )
        mark_backtest_run_running(session, run)

        result = BacktestRunResult(
            run_status="succeeded",
            strategy_name="fixture_strategy",
            strategy_version="0.1.0",
            candle_count=20,
            detected_setups=[
                _v1_setup_payload("TBXBTV1-triggered-stop", "triggered"),
                _v1_setup_payload("TBXBTV1-triggered-target", "triggered"),
                _v1_setup_payload("TBXBTV1-triggered-same", "triggered"),
                _v1_setup_payload("TBXBTV1-triggered-session", "triggered"),
                _v1_setup_payload("TBXBTV1-pending", "pending_entry"),
                _v1_setup_payload(
                    "TBXBTV1-expired",
                    "expired",
                    rejection_reason="entry_not_triggered",
                ),
                _v1_setup_payload(
                    "TBXBTV1-filtered",
                    "filtered_out",
                    rejection_reason="ema_context_failed",
                ),
                _v1_setup_payload(
                    "TBXBTV1-invalidated",
                    "invalidated",
                    rejection_reason="anchor_high_broken_before_entry",
                ),
            ],
            simulated_trades=[
                _v1_trade_payload("TBXBTV1-trade-stop", "TBXBTV1-triggered-stop", "stop_hit"),
                _v1_trade_payload(
                    "TBXBTV1-trade-target",
                    "TBXBTV1-triggered-target",
                    "target_hit",
                ),
                _v1_trade_payload(
                    "TBXBTV1-trade-same",
                    "TBXBTV1-triggered-same",
                    "same_candle_stop",
                    same_candle_stop_target=True,
                ),
                _v1_trade_payload(
                    "TBXBTV1-trade-session",
                    "TBXBTV1-triggered-session",
                    "session_force_close",
                ),
            ],
            metrics={
                "skipped_symbol_days": [
                    {
                        "instrument_id": instrument_id,
                        "symbol": "TBXBTV1",
                        "trade_date": skipped_trade_date,
                        "reason": "missing_required_context",
                        "missing_context": ["previous_day_levels"],
                    }
                ],
            },
        )

        counts = write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result)
        session.commit()
        session.refresh(run)

        setups = session.query(DetectedSetup).filter_by(backtest_run_id=run.id).all()
        trades = session.query(SimulatedTrade).filter_by(backtest_run_id=run.id).all()
        setup_statuses = {setup.setup_status for setup in setups}
        setup_session_dates = {setup.session_date.isoformat() for setup in setups}
        exit_reasons = {trade.exit_reason for trade in trades}
        rejection_reasons = {setup.rejection_reason for setup in setups if setup.rejection_reason}
        setup_metadata = {setup.setup_key: dict(setup.setup_metadata_json) for setup in setups}
        trade_metadata = {trade.trade_key: dict(trade.trade_metadata_json) for trade in trades}
        metrics = dict(run.metrics_json)

    assert counts == {"detected_setup_count": 8, "simulated_trade_count": 4}
    assert setup_statuses == {
        "pending_entry",
        "triggered",
        "expired",
        "filtered_out",
        "invalidated",
    }
    assert exit_reasons == {
        "stop_hit",
        "target_hit",
        "same_candle_stop",
        "session_force_close",
    }
    assert rejection_reasons == {
        "entry_not_triggered",
        "ema_context_failed",
        "anchor_high_broken_before_entry",
    }
    assert skipped_trade_date not in setup_session_dates
    assert setup_metadata["TBXBTV1-filtered"]["filters"]["ema_context"]["passed"] is False
    assert trade_metadata["TBXBTV1-trade-same"]["same_candle_stop_target"] is True
    assert metrics["skipped_symbol_days"] == [
        {
            "instrument_id": instrument_id,
            "symbol": "TBXBTV1",
            "trade_date": skipped_trade_date,
            "reason": "missing_required_context",
            "missing_context": ["previous_day_levels"],
        }
    ]


def test_backtest_result_persistence_accepts_real_two_legged_pullback_output() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTREAL")
        config = _config(
            partition.id,
            strategy_name="two_legged_pullback",
            parameters={
                "use_anchor_context": False,
                "use_ema_context": False,
                "use_min_anchor_range_filter": False,
                "use_raw_leg_chop_filter": False,
            },
        )
        run = create_backtest_run_from_config(
            session,
            instrument_id=instrument.id,
            config=config,
            input_data_snapshot=build_backtest_input_snapshot(partition),
        )
        mark_backtest_run_running(session, run)

        result = BacktestRunner(strategy=TwoLeggedPullbackStrategy()).run(
            config=config,
            candles=_two_legged_pullback_candles(),
        )
        counts = write_backtest_results(session, run, result)
        mark_backtest_run_succeeded(session, run, result)
        session.commit()

        setup = session.query(DetectedSetup).filter_by(backtest_run_id=run.id).one()
        trade = session.query(SimulatedTrade).filter_by(backtest_run_id=run.id).one()
        setup_id = setup.id
        setup_status = setup.setup_status
        setup_metadata = dict(setup.setup_metadata_json)
        trade_detected_setup_id = trade.detected_setup_id
        trade_exit_reason = trade.exit_reason
        trade_quantity = trade.quantity
        trade_metadata = dict(trade.trade_metadata_json)

    assert counts == {"detected_setup_count": 1, "simulated_trade_count": 1}
    assert setup_status == "triggered"
    assert setup_metadata["context"]["ema20_at_signal"] is not None
    assert setup_metadata["context"]["vwap_at_signal"] is not None
    assert setup_metadata["planned_trade"]["target_r_multiple"] == 2.0
    assert trade_exit_reason == "target_hit"
    assert trade_quantity == Decimal("1.000000")
    assert trade_detected_setup_id == setup_id
    assert trade_metadata["entry_reason"] == "signal_bar_break"
    assert trade_metadata["pnl_semantics"] == "normalized_one_share"
    assert trade_metadata["position_sizing_mode"] == "fixed_quantity_1"
    assert trade_metadata["fees_included"] is False
    assert trade_metadata["slippage_included"] is False


def test_backtest_result_persistence_requires_explicit_setup_status() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTNOSTATUS")
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
            detected_setups=[
                {
                    "setup_key": "TBXBTNOSTATUS-setup",
                    "side": "long",
                    "detected_at": datetime(2024, 1, 2, 14, 35, tzinfo=UTC),
                }
            ],
            simulated_trades=[],
            metrics={},
        )

        try:
            write_backtest_results(session, run, result)
        except BacktestResultPersistenceError as exc:
            assert "setup_status" in str(exc)
        else:
            raise AssertionError("Expected BacktestResultPersistenceError.")


def test_backtest_result_persistence_rejects_invalid_setup_status() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTBADSTATUS")
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
            detected_setups=[
                _v1_setup_payload("TBXBTBADSTATUS-setup", "not_a_valid_status"),
            ],
            simulated_trades=[],
            metrics={},
        )

        try:
            write_backtest_results(session, run, result)
        except IntegrityError as exc:
            assert "ck_detected_setups_setup_status_allowed" in str(exc)
        else:
            raise AssertionError("Expected IntegrityError.")


def test_backtest_result_persistence_rejects_invalid_exit_reason() -> None:
    with _db_session() as session:
        instrument, partition = _create_instrument_and_partition(session, symbol="TBXBTBADREASON")
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
            detected_setups=[
                _v1_setup_payload("TBXBTBADREASON-setup", "triggered"),
            ],
            simulated_trades=[
                _v1_trade_payload(
                    "TBXBTBADREASON-trade",
                    "TBXBTBADREASON-setup",
                    "not_a_valid_exit_reason",
                )
            ],
            metrics={},
        )

        try:
            write_backtest_results(session, run, result)
        except IntegrityError as exc:
            assert "ck_simulated_trades_exit_reason_allowed" in str(exc)
        else:
            raise AssertionError("Expected IntegrityError.")


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
                "strategy_name": "noop",
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
        session.execute(delete(SimulatedTrade).where(SimulatedTrade.trade_key.like("TBXBT%")))
        session.execute(delete(DetectedSetup).where(DetectedSetup.setup_key.like("TBXBT%")))
        session.execute(delete(BacktestRun).where(BacktestRun.strategy_name == "noop"))
        session.execute(delete(BacktestRun).where(BacktestRun.strategy_name == "fixture_strategy"))
        session.execute(
            delete(BacktestRun).where(BacktestRun.strategy_name == "two_legged_pullback")
        )
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


def _config(
    partition_id: uuid.UUID,
    *,
    strategy_name: str = "noop",
    parameters: dict[str, object] | None = None,
) -> BacktestConfig:
    return BacktestConfig.create(
        symbol="SPY",
        timeframe="1m",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 14, 31, tzinfo=UTC),
        clean_data_partition_id=partition_id,
        strategy_name=strategy_name,
        parameters=parameters,
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


def _two_legged_pullback_candles() -> list[BacktestCandle]:
    candles = [
        _strategy_candle(index, open_price=99.5, high=100.0, low=99.0, close=99.5)
        for index in range(480)
    ]
    pattern = [
        _strategy_candle(90, open_price=99.5, high=100.0, low=99.0, close=99.4),
        _strategy_candle(91, open_price=99.4, high=99.8, low=98.8, close=99.0),
        _strategy_candle(92, open_price=99.0, high=99.5, low=98.5, close=98.7),
        _strategy_candle(93, open_price=98.8, high=99.6, low=98.6, close=99.4),
        _strategy_candle(94, open_price=99.4, high=100.0, low=98.9, close=99.8),
        _strategy_candle(95, open_price=99.7, high=99.9, low=98.7, close=99.0),
        _strategy_candle(96, open_price=99.0, high=99.8, low=98.4, close=98.8),
        _strategy_candle(97, open_price=99.6, high=99.9, low=99.5, close=99.8),
        _strategy_candle(98, open_price=99.9, high=100.1, low=99.7, close=100.0),
        _strategy_candle(99, open_price=100.0, high=100.8, low=99.9, close=100.7),
    ]
    candles[90:100] = pattern
    for index in range(100, len(candles)):
        candles[index] = _strategy_candle(
            index,
            open_price=100.1,
            high=100.8,
            low=99.9,
            close=100.1,
        )
    return candles


def _strategy_candle(
    offset_minutes: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> BacktestCandle:
    return BacktestCandle(
        symbol="SPY",
        ts_event=datetime(2024, 1, 2, 13, 0, tzinfo=UTC) + timedelta(minutes=offset_minutes),
        session_date=date(2024, 1, 2),
        timeframe="1m",
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def _v1_setup_payload(
    setup_key: str,
    setup_status: str,
    *,
    rejection_reason: str | None = None,
) -> dict[str, object]:
    return {
        "setup_key": setup_key,
        "setup_status": setup_status,
        "side": "long",
        "detected_at": datetime(2024, 1, 2, 14, 35, tzinfo=UTC),
        "setup_start_at": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        "setup_end_at": datetime(2024, 1, 2, 14, 35, tzinfo=UTC),
        "entry_price": "100.50",
        "stop_price": "99.90",
        "target_price": "101.70",
        "setup_metadata_json": {
            "anchors": {
                "high": "101.00",
                "low": "99.75",
            },
            "legs": {
                "raw_leg_1": "down",
                "raw_leg_2": "down",
            },
            "signal_bar": {
                "ts_event": "2024-01-02T14:35:00+00:00",
                "high": "100.50",
            },
            "context": {
                "ema20": "100.25",
                "vwap": "100.10",
            },
            "filters": {
                "ema_context": {
                    "passed": setup_status != "filtered_out",
                },
            },
        },
        "rejection_reason": rejection_reason,
    }


def _v1_trade_payload(
    trade_key: str,
    detected_setup_key: str,
    exit_reason: str,
    *,
    same_candle_stop_target: bool = False,
) -> dict[str, object]:
    return {
        "trade_key": trade_key,
        "detected_setup_key": detected_setup_key,
        "trade_status": "closed",
        "side": "long",
        "entry_at": datetime(2024, 1, 2, 14, 36, tzinfo=UTC),
        "entry_price": "100.50",
        "exit_at": datetime(2024, 1, 2, 14, 40, tzinfo=UTC),
        "exit_price": "99.90" if exit_reason in {"stop_hit", "same_candle_stop"} else "101.70",
        "stop_price": "99.90",
        "target_price": "101.70",
        "risk_amount": "6.00",
        "r_multiple": "-1.0" if exit_reason in {"stop_hit", "same_candle_stop"} else "2.0",
        "exit_reason": exit_reason,
        "trade_metadata_json": {
            "entry_gap_fill": False,
            "stop_gap_fill": False,
            "target_gap_fill": False,
            "same_candle_stop_target": same_candle_stop_target,
            "planned_vs_actual_entry": {
                "planned": "100.50",
                "actual": "100.50",
            },
        },
    }
