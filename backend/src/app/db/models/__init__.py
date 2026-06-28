"""SQLAlchemy ORM model imports for Alembic metadata discovery."""

from app.db.models.backtest_run import BacktestRun
from app.db.models.data_partition import DataPartition
from app.db.models.detected_setup import DetectedSetup
from app.db.models.instrument import Instrument
from app.db.models.pipeline_run import PipelineRun
from app.db.models.simulated_trade import SimulatedTrade

__all__ = [
    "BacktestRun",
    "DataPartition",
    "DetectedSetup",
    "Instrument",
    "PipelineRun",
    "SimulatedTrade",
]
