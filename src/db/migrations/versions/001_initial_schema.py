"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # product_groups
    op.create_table(
        "product_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # restaurants
    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("opened_on", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # skus
    op.create_table(
        "skus",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "product_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_groups.id"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # daily_sales
    op.create_table(
        "daily_sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "restaurant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skus.id"),
            nullable=False,
        ),
        sa.Column("sale_date", sa.Date, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("revenue", sa.Numeric(14, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "sku_id", "sale_date", name="uq_daily_sale"),
    )
    op.create_index("ix_daily_sales_lookup", "daily_sales", ["restaurant_id", "sku_id", "sale_date"])

    # run_status enum
    op.execute("CREATE TYPE run_status AS ENUM ('pending', 'running', 'complete', 'failed')")

    # forecast_runs
    op.create_table(
        "forecast_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("triggered_by", sa.String(100), nullable=False, server_default="manual"),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "running", "complete", "failed", name="run_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # forecast_values
    op.create_table(
        "forecast_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "restaurant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skus.id"),
            nullable=False,
        ),
        sa.Column("forecast_date", sa.Date, nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("quantity_p50", sa.Numeric(14, 4), nullable=False),
        sa.Column("quantity_p10", sa.Numeric(14, 4), nullable=True),
        sa.Column("quantity_p90", sa.Numeric(14, 4), nullable=True),
        sa.Column("is_reconciled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_forecast_values_run", "forecast_values", ["run_id", "restaurant_id", "sku_id"])

    # model_assignments
    op.create_table(
        "model_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "restaurant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("restaurants.id"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skus.id"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("mlflow_run_id", sa.String(200), nullable=True),
        sa.Column("selection_reason", sa.Text, nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_model_assignments_run", "model_assignments", ["run_id"])


def downgrade() -> None:
    op.drop_table("model_assignments")
    op.drop_table("forecast_values")
    op.drop_table("forecast_runs")
    op.execute("DROP TYPE run_status")
    op.drop_table("daily_sales")
    op.drop_table("skus")
    op.drop_table("restaurants")
    op.drop_table("product_groups")
