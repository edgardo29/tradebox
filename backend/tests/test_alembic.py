from pathlib import Path

from alembic.config import Config
from app.db.base import Base


def test_alembic_config_points_to_backend_alembic_directory() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(backend_root / "alembic.ini")
    script_location = alembic_config.get_main_option("script_location")

    assert script_location == "alembic"
    assert (backend_root / script_location).is_dir()


def test_alembic_metadata_is_backend_db_metadata() -> None:
    assert Base.metadata is not None
