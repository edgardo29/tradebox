from app.db import models
from app.db.base import Base


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
