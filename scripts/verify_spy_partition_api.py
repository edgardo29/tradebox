"""Verify backend API metadata for the completed SPY raw + clean partition."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataPartition, Instrument
from app.db.session import SessionLocal
from app.main import app


def _load_local_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def main() -> int:
    _load_local_env_file()

    session = SessionLocal()
    try:
        partition = _load_latest_spy_partition(session)
        client = TestClient(app)

        by_id_response = client.get(f"/data-partitions/{partition.id}")
        by_id_response.raise_for_status()
        by_id = by_id_response.json()

        list_response = client.get(
            "/data-partitions",
            params={
                "symbol": "SPY",
                "vendor": "databento",
                "timeframe": "1m",
                "session_date": str(partition.session_date),
                "partition_status": "validated",
            },
        )
        list_response.raise_for_status()
        matching = [row for row in list_response.json() if row["id"] == str(partition.id)]
        if len(matching) != 1:
            raise RuntimeError("SPY partition was not found exactly once in filtered API list.")

        _assert_completed_metadata(by_id)

        print("SPY data_partitions API verification succeeded.")
        print(f"partition_id={by_id['id']}")
        print(f"instrument_symbol={by_id['instrument_symbol']}")
        print(f"raw_object_path={by_id['raw_object_path']}")
        print(f"clean_object_path={by_id['clean_object_path']}")
        print(f"raw_file_format={by_id['raw_file_format']}")
        print(f"clean_file_format={by_id['clean_file_format']}")
        print(f"partition_status={by_id['partition_status']}")
        print(f"row_count={by_id['row_count']}")
        print(f"validation_error_count={by_id['validation_error_count']}")
        return 0
    except Exception as exc:
        print(f"SPY data_partitions API verification failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


def _load_latest_spy_partition(session: Session) -> DataPartition:
    statement = (
        select(DataPartition)
        .join(Instrument, DataPartition.instrument_id == Instrument.id)
        .where(
            Instrument.symbol == "SPY",
            DataPartition.vendor == "databento",
            DataPartition.raw_object_path.is_not(None),
            DataPartition.clean_object_path.is_not(None),
        )
        .order_by(DataPartition.updated_at.desc())
    )
    partition = session.scalars(statement).first()
    if partition is None:
        raise RuntimeError("No completed SPY Databento partition was found.")
    return partition


def _assert_completed_metadata(row: dict[str, object]) -> None:
    required_values = [
        "id",
        "instrument_id",
        "instrument_symbol",
        "vendor",
        "dataset",
        "timeframe",
        "session_date",
        "raw_object_path",
        "clean_object_path",
        "raw_file_format",
        "clean_file_format",
        "partition_status",
        "row_count",
        "validation_error_count",
        "schema_version",
        "raw_content_hash",
        "clean_content_hash",
        "created_at",
        "updated_at",
    ]
    missing = [field for field in required_values if row.get(field) in {None, ""}]
    if missing:
        raise RuntimeError(f"Completed SPY partition API response is missing: {missing}")

    serialized = str(row).lower()
    forbidden_tokens = ["access_key", "secret_access_key", "databento_api_key"]
    leaked = [token for token in forbidden_tokens if token in serialized]
    if leaked:
        raise RuntimeError(f"API response includes secret-looking tokens: {leaked}")


if __name__ == "__main__":
    raise SystemExit(main())
