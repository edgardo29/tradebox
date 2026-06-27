from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, create_app


def test_create_app() -> None:
    created_app = create_app()

    assert isinstance(created_app, FastAPI)


def test_app_object_imports() -> None:
    assert isinstance(app, FastAPI)


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
