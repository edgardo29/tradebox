from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.db.base import Base

EXPECTED_TABLE_REVISIONS = {
    "0001_instruments_table": None,
    "0002_pipeline_runs_table": "0001_instruments_table",
    "0003_data_partitions_table": "0002_pipeline_runs_table",
    "0004_backtest_runs_table": "0003_data_partitions_table",
    "0005_detected_setups_table": "0004_backtest_runs_table",
    "0006_simulated_trades_table": "0005_detected_setups_table",
}


def test_alembic_config_points_to_backend_alembic_directory() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(backend_root / "alembic.ini")
    script_location = alembic_config.get_main_option("script_location")

    assert script_location == "alembic"
    assert (backend_root / script_location).is_dir()


def test_alembic_metadata_is_backend_db_metadata() -> None:
    assert Base.metadata is not None


def test_alembic_has_single_linear_table_revision_chain() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(backend_root / "alembic.ini")
    script = ScriptDirectory.from_config(alembic_config)

    assert script.get_bases() == ["0001_instruments_table"]
    assert script.get_heads() == ["0006_simulated_trades_table"]

    for revision, down_revision in EXPECTED_TABLE_REVISIONS.items():
        script_revision = script.get_revision(revision)

        assert script_revision is not None
        assert script_revision.down_revision == down_revision

    old_combined_migration = (
        backend_root / "alembic" / "versions" / "0001_create_core_trading_tables.py"
    )
    assert not old_combined_migration.exists()
