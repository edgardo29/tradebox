from app.db import models
from app.db.base import Base


def _check_constraint_sql(model: type, constraint_name: str) -> str:
    for constraint in model.__table__.constraints:
        if constraint.name == constraint_name:
            return str(constraint.sqltext)
    raise AssertionError(f"Missing check constraint: {constraint_name}")


def test_core_models_are_registered_in_metadata() -> None:
    expected_tables = {
        "instruments",
        "pipeline_runs",
        "data_partitions",
        "backtest_runs",
        "detected_setups",
        "simulated_trades",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_model_table_names() -> None:
    assert models.Instrument.__tablename__ == "instruments"
    assert models.PipelineRun.__tablename__ == "pipeline_runs"
    assert models.DataPartition.__tablename__ == "data_partitions"
    assert models.BacktestRun.__tablename__ == "backtest_runs"
    assert models.DetectedSetup.__tablename__ == "detected_setups"
    assert models.SimulatedTrade.__tablename__ == "simulated_trades"


def test_detected_setup_status_constraint_allows_v1_and_legacy_statuses() -> None:
    constraint_sql = _check_constraint_sql(
        models.DetectedSetup,
        "ck_detected_setups_setup_status_allowed",
    )

    for status in (
        "pending_entry",
        "triggered",
        "expired",
        "filtered_out",
        "invalidated",
        "detected",
        "rejected",
        "skipped",
    ):
        assert f"'{status}'" in constraint_sql


def test_detected_setup_status_requires_explicit_value() -> None:
    setup_status = models.DetectedSetup.__table__.columns["setup_status"]

    assert setup_status.nullable is False
    assert setup_status.server_default is None


def test_simulated_trade_exit_reason_constraint_allows_v1_and_legacy_reasons() -> None:
    constraint_sql = _check_constraint_sql(
        models.SimulatedTrade,
        "ck_simulated_trades_exit_reason_allowed",
    )

    for exit_reason in (
        "stop_hit",
        "target_hit",
        "same_candle_stop",
        "session_force_close",
        "session_close",
        "invalidation",
        "end_of_data",
        "manual_rule_exit",
        "cancelled",
    ):
        assert f"'{exit_reason}'" in constraint_sql


def test_v1_persistence_json_columns_are_registered_in_metadata() -> None:
    assert "setup_metadata_json" in models.DetectedSetup.__table__.columns
    assert "trade_metadata_json" in models.SimulatedTrade.__table__.columns
    assert "metrics_json" in models.BacktestRun.__table__.columns
