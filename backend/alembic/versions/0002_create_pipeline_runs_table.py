"""Create pipeline runs table.

Revision ID: 0002_pipeline_runs_table
Revises: 0001_instruments_table
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_pipeline_runs_table"
down_revision: str | None = "0001_instruments_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column(
            "run_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("dagster_run_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            "run_type IN ('market_data_ingestion', 'raw_to_clean_conversion', "
            "'setup_detection', 'backtest', 'manual')",
            name="ck_pipeline_runs_run_type_allowed",
        ),
        sa.CheckConstraint(
            "run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_run_status_allowed",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_runs_finished_at_after_started_at",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_runs"),
        sa.UniqueConstraint("dagster_run_id", name="uq_pipeline_runs_dagster_run_id"),
    )
    op.create_index("ix_pipeline_runs_run_type", "pipeline_runs", ["run_type"])
    op.create_index("ix_pipeline_runs_run_status", "pipeline_runs", ["run_status"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.create_index(
        "ix_pipeline_runs_run_type_run_status", "pipeline_runs", ["run_type", "run_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_run_type_run_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_type", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
