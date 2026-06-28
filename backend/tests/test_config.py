from app.config import Settings


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test_user:test_password@localhost:5432/test_db",
    )

    settings = Settings()

    assert (
        settings.database_url
        == "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"
    )
