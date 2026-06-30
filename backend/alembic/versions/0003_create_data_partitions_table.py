"""Create data partitions table.

Revision ID: 0003_data_partitions_table
Revises: 0002_pipeline_runs_table
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_data_partitions_table"
down_revision: str | None = "0002_pipeline_runs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_partitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=128), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("raw_object_path", sa.Text(), nullable=True),
        sa.Column("clean_object_path", sa.Text(), nullable=True),
        sa.Column("raw_file_format", sa.String(length=32), nullable=True),
        sa.Column("clean_file_format", sa.String(length=32), nullable=True),
        sa.Column(
            "partition_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("validation_error_count", sa.BigInteger(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("raw_content_hash", sa.String(length=128), nullable=True),
        sa.Column("clean_content_hash", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "vendor IN ('databento', 'manual', 'test')", name="ck_data_partitions_vendor_allowed"
        ),
        sa.CheckConstraint(
            "timeframe IN ('1m', '5m')", name="ck_data_partitions_timeframe_allowed"
        ),
        sa.CheckConstraint(
            "partition_status IN ('pending', 'raw_available', 'clean_available', "
            "'validated', 'failed')",
            name="ck_data_partitions_partition_status_allowed",
        ),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0", name="ck_data_partitions_row_count_non_negative"
        ),
        sa.CheckConstraint(
            "validation_error_count IS NULL OR validation_error_count >= 0",
            name="ck_data_partitions_validation_error_count_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_data_partitions_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name="fk_data_partitions_pipeline_run_id_pipeline_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_partitions"),
        sa.UniqueConstraint(
            "instrument_id",
            "vendor",
            "dataset",
            "timeframe",
            "session_date",
            name="uq_data_partitions_inst_vendor_dataset_timeframe_date",
        ),
    )
    op.create_index("ix_data_partitions_instrument_id", "data_partitions", ["instrument_id"])
    op.create_index("ix_data_partitions_pipeline_run_id", "data_partitions", ["pipeline_run_id"])
    op.create_index("ix_data_partitions_session_date", "data_partitions", ["session_date"])
    op.create_index("ix_data_partitions_partition_status", "data_partitions", ["partition_status"])
    op.create_index("ix_data_partitions_timeframe", "data_partitions", ["timeframe"])
    op.create_index(
        "ix_data_partitions_vendor_dataset_timeframe",
        "data_partitions",
        ["vendor", "dataset", "timeframe"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_partitions_vendor_dataset_timeframe", table_name="data_partitions")
    op.drop_index("ix_data_partitions_timeframe", table_name="data_partitions")
    op.drop_index("ix_data_partitions_partition_status", table_name="data_partitions")
    op.drop_index("ix_data_partitions_session_date", table_name="data_partitions")
    op.drop_index("ix_data_partitions_pipeline_run_id", table_name="data_partitions")
    op.drop_index("ix_data_partitions_instrument_id", table_name="data_partitions")
    op.drop_table("data_partitions")
