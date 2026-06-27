from sqlalchemy import Engine, MetaData
from sqlalchemy.orm import Session

from app.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db_session


def test_base_metadata_exists() -> None:
    assert isinstance(Base.metadata, MetaData)


def test_engine_is_configured() -> None:
    assert isinstance(engine, Engine)
    assert engine.url.render_as_string(hide_password=False) == settings.database_url


def test_session_dependency_yields_session() -> None:
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        assert isinstance(session, Session)
        assert SessionLocal.kw["bind"] is engine
    finally:
        session_generator.close()
