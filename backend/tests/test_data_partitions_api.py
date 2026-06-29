from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import DataPartition, Instrument
from app.db.session import SessionLocal
from app.main import app
from app.schemas.data_partition import DataPartitionCreate
from app.services.data_partitions import upsert_data_partition


@pytest.fixture()
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            delete(DataPartition).where(
                DataPartition.vendor == "test",
                DataPartition.dataset.like("api_test%"),
            )
        )
        session.execute(delete(Instrument).where(Instrument.symbol.like("TBXAPI%")))
        session.commit()
        session.close()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_list_data_partitions_returns_response_shape(
    client: TestClient, db_session: Session
) -> None:
    partition = _create_partition(db_session, symbol="TBXAPI1")

    response = client.get("/data-partitions")

    assert response.status_code == 200
    rows = response.json()
    matching = [row for row in rows if row["id"] == str(partition.id)]
    assert len(matching) == 1
    assert matching[0] == {
        "id": str(partition.id),
        "instrument_id": str(partition.instrument_id),
        "instrument_symbol": "TBXAPI1",
        "pipeline_run_id": None,
        "vendor": "test",
        "dataset": "api_test",
        "timeframe": "1m",
        "session_date": "2026-06-28",
        "raw_object_path": "dev/smoke-tests/api-test.txt",
        "clean_object_path": None,
        "raw_file_format": "txt",
        "clean_file_format": None,
        "partition_status": "raw_available",
        "row_count": 1,
        "validation_error_count": 0,
        "schema_version": "1",
        "raw_content_hash": "abc123",
        "clean_content_hash": None,
        "error_message": None,
        "created_at": matching[0]["created_at"],
        "updated_at": matching[0]["updated_at"],
    }


def test_get_data_partition_by_id(client: TestClient, db_session: Session) -> None:
    partition = _create_partition(db_session, symbol="TBXAPI2")

    response = client.get(f"/data-partitions/{partition.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(partition.id)
    assert response.json()["instrument_symbol"] == "TBXAPI2"
    assert response.json()["raw_object_path"] == "dev/smoke-tests/api-test.txt"


def test_list_data_partitions_filters_by_metadata(
    client: TestClient, db_session: Session
) -> None:
    partition = _create_partition(db_session, symbol="TBXAPI3")
    _create_partition(
        db_session,
        symbol="TBXAPI4",
        dataset="api_test_other",
        session_date=date(2026, 6, 29),
    )

    response = client.get(
        "/data-partitions",
        params={
            "instrument_id": str(partition.instrument_id),
            "symbol": "TBXAPI3",
            "vendor": "test",
            "dataset": "api_test",
            "timeframe": "1m",
            "session_date": "2026-06-28",
            "partition_status": "raw_available",
        },
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [str(partition.id)]


@pytest.mark.parametrize(
    ("filter_name", "filter_value"),
    [
        ("vendor", "test"),
        ("dataset", "api_test"),
        ("timeframe", "1m"),
        ("session_date", "2026-06-28"),
        ("partition_status", "raw_available"),
    ],
)
def test_list_data_partitions_supports_individual_filters(
    client: TestClient,
    db_session: Session,
    filter_name: str,
    filter_value: str,
) -> None:
    partition = _create_partition(db_session, symbol=f"TBXAPI{filter_name.upper()[:4]}")

    response = client.get("/data-partitions", params={filter_name: filter_value})

    assert response.status_code == 200
    assert str(partition.id) in {row["id"] for row in response.json()}


def test_list_data_partitions_filters_by_symbol(client: TestClient, db_session: Session) -> None:
    partition = _create_partition(db_session, symbol="TBXAPISPY")
    _create_partition(db_session, symbol="TBXAPIQQQ")

    response = client.get("/data-partitions", params={"symbol": "tbxapispy"})

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [str(partition.id)]


def test_data_partition_response_includes_raw_and_clean_metadata(
    client: TestClient, db_session: Session
) -> None:
    partition = _create_partition(
        db_session,
        symbol="TBXAPICLEAN",
        clean_object_path=(
            "clean/vendor=databento/dataset=EQUS.MINI/symbol=SPY/timeframe=1m/"
            "session_date=2024-01-02/part-000.parquet"
        ),
        clean_file_format="parquet",
        clean_content_hash="clean456",
        partition_status="validated",
    )

    response = client.get(f"/data-partitions/{partition.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["raw_object_path"] == "dev/smoke-tests/api-test.txt"
    assert body["clean_object_path"] == (
        "clean/vendor=databento/dataset=EQUS.MINI/symbol=SPY/timeframe=1m/"
        "session_date=2024-01-02/part-000.parquet"
    )
    assert body["raw_file_format"] == "txt"
    assert body["clean_file_format"] == "parquet"
    assert body["partition_status"] == "validated"
    assert body["clean_content_hash"] == "clean456"
    assert body["row_count"] == 1
    assert body["validation_error_count"] == 0


def test_data_partition_response_does_not_expose_secret_values(
    client: TestClient, db_session: Session
) -> None:
    partition = _create_partition(db_session, symbol="TBXAPISAFE")

    response = client.get(f"/data-partitions/{partition.id}")

    assert response.status_code == 200
    serialized = str(response.json()).lower()
    assert "secret" not in serialized
    assert "access_key" not in serialized
    assert "r2_secret_access_key" not in serialized
    assert "databento_api_key" not in serialized


def test_get_data_partition_returns_404_for_missing_id(client: TestClient) -> None:
    response = client.get(f"/data-partitions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Data partition not found."}


def _create_partition(
    session: Session,
    *,
    symbol: str,
    dataset: str = "api_test",
    session_date: date = date(2026, 6, 28),
    clean_object_path: str | None = None,
    clean_file_format: str | None = None,
    clean_content_hash: str | None = None,
    partition_status: str = "raw_available",
) -> DataPartition:
    instrument = Instrument(
        symbol=symbol,
        name=f"{symbol} Smoke Instrument",
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
            dataset=dataset,
            timeframe="1m",
            session_date=session_date,
            raw_object_path="dev/smoke-tests/api-test.txt",
            clean_object_path=clean_object_path,
            raw_file_format="txt",
            clean_file_format=clean_file_format,
            partition_status=partition_status,
            row_count=1,
            validation_error_count=0,
            schema_version="1",
            raw_content_hash="abc123",
            clean_content_hash=clean_content_hash,
        ),
    )
    session.commit()
    session.refresh(partition)
    return partition
