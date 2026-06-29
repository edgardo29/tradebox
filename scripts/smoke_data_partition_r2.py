"""Run a live R2 plus Postgres data partition catalog smoke test."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import DataPartition, Instrument
from app.db.session import SessionLocal
from app.schemas.data_partition import DataPartitionCreate
from app.services.data_partitions import get_data_partition, upsert_data_partition
from shared_core.storage import R2ConfigError, load_r2_config_from_env, sha256_text
from shared_core.storage.object_keys import smoke_test_object_key
from shared_core.storage.r2_client import R2StorageClient

SMOKE_SYMBOL = "TBXSMOKE"
SMOKE_VENDOR = "test"
SMOKE_DATASET = "smoke_test"
SMOKE_TIMEFRAME = "1m"
SMOKE_SCHEMA_VERSION = "1"


def _load_local_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a tiny R2 object, catalog it in data_partitions, read it back, and clean up."
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep the smoke-test R2 object and data_partitions row for manual inspection.",
    )
    args = parser.parse_args()

    _load_local_env_file()

    try:
        config = load_r2_config_from_env()
    except R2ConfigError as exc:
        print(f"R2 configuration error: {exc}", file=sys.stderr)
        return 2

    object_key = smoke_test_object_key(f"data-partition-{uuid4().hex}.txt")
    content = f"tradebox data partition smoke test {datetime.now(UTC).isoformat()}\n"
    content_hash = sha256_text(content)
    r2_client = R2StorageClient(config)

    session = SessionLocal()
    partition_id = None
    object_uploaded = False

    try:
        r2_client.upload_text(object_key, content)
        object_uploaded = True
        if r2_client.read_text(object_key) != content:
            raise RuntimeError("R2 readback did not match uploaded smoke-test content.")
        if not r2_client.object_exists(object_key):
            raise RuntimeError("R2 smoke-test object was not visible through head_object.")

        instrument = _get_or_create_smoke_instrument(session)
        partition = upsert_data_partition(
            session,
            DataPartitionCreate(
                instrument_id=instrument.id,
                vendor=SMOKE_VENDOR,
                dataset=SMOKE_DATASET,
                timeframe=SMOKE_TIMEFRAME,
                session_date=date.today(),
                raw_object_path=object_key,
                raw_file_format="txt",
                partition_status="raw_available",
                row_count=1,
                validation_error_count=0,
                schema_version=SMOKE_SCHEMA_VERSION,
                raw_content_hash=content_hash,
            ),
            commit=True,
        )
        partition_id = partition.id

        loaded_partition = get_data_partition(session, partition.id)
        if loaded_partition is None:
            raise RuntimeError("Created data_partitions row could not be read back.")
        if loaded_partition.raw_object_path != object_key:
            raise RuntimeError("Readback data_partitions row has the wrong raw_object_path.")
        if loaded_partition.raw_content_hash != content_hash:
            raise RuntimeError("Readback data_partitions row has the wrong raw_content_hash.")

        print("R2 plus data_partitions smoke test succeeded.")
        print(f"bucket={config.bucket_name}")
        print(f"object_key={object_key}")
        print(f"instrument_id={instrument.id}")
        print(f"data_partition_id={loaded_partition.id}")
        print(f"raw_content_hash={content_hash}")
        if args.keep_artifacts:
            print("Artifacts kept for inspection because --keep-artifacts was set.")
        else:
            print("Smoke-test object and data_partitions row will be cleaned up.")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"R2 plus data_partitions smoke test failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_artifacts:
            _cleanup_smoke_artifacts(
                session,
                partition_id=partition_id,
                object_uploaded=object_uploaded,
                object_key=object_key,
                r2_client=r2_client,
            )
        session.close()


def _get_or_create_smoke_instrument(session: Session) -> Instrument:
    instrument = session.scalars(select(Instrument).where(Instrument.symbol == SMOKE_SYMBOL)).one_or_none()
    if instrument is not None:
        return instrument

    instrument = Instrument(
        symbol=SMOKE_SYMBOL,
        name="tradebox smoke test instrument",
        asset_class="equity",
        exchange="TEST",
    )
    session.add(instrument)
    session.flush()
    return instrument


def _cleanup_smoke_artifacts(
    session: Session,
    *,
    partition_id: object | None,
    object_uploaded: bool,
    object_key: str,
    r2_client: R2StorageClient,
) -> None:
    if partition_id is not None:
        session.execute(delete(DataPartition).where(DataPartition.id == partition_id))
        session.commit()

    if object_uploaded:
        r2_client.delete_object(object_key)


if __name__ == "__main__":
    raise SystemExit(main())
