"""Celery task: run_forecast_pipeline.

Loads all sales from Postgres, trains every restaurant×SKU series via
train_all_series(), persists ForecastValue rows, and updates the ForecastRun status.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import pandas as pd
from celery import Task
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.db.models.forecast import ForecastRun, ForecastValue, RunStatus
from src.db.models.sales import DailySale
from src.ml.training.trainer import TrainConfig, train_all_series
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.run_forecast_pipeline", queue="forecast")  # type: ignore[misc]
def run_forecast_pipeline(self: Task, run_id: str) -> dict:
    """Train all series and persist forecast values."""
    settings = get_settings()
    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    run_uuid = uuid.UUID(run_id)

    with Session(engine) as session:
        # Mark running
        session.execute(
            update(ForecastRun)
            .where(ForecastRun.id == run_uuid)
            .values(
                status=RunStatus.running,
                started_at=datetime.now(timezone.utc),
                celery_task_id=self.request.id,
            )
        )
        session.commit()

        try:
            rows = session.execute(
                select(
                    DailySale.restaurant_id,
                    DailySale.sku_id,
                    DailySale.sale_date,
                    DailySale.quantity,
                )
            ).all()

            if not rows:
                raise ValueError("No sales data found in database")

            sales_df = pd.DataFrame(
                rows, columns=["restaurant_id", "sku_id", "sale_date", "quantity"]
            )
            sales_df["restaurant_id"] = sales_df["restaurant_id"].astype(str)
            sales_df["sku_id"] = sales_df["sku_id"].astype(str)
            sales_df["quantity"] = sales_df["quantity"].astype(float)
            sales_df["sale_date"] = pd.to_datetime(sales_df["sale_date"])

            config = TrainConfig(
                horizon_days=settings.default_horizon_days,
                n_cv_folds=settings.default_cv_folds,
            )

            results = train_all_series(
                all_sales_df=sales_df,
                config=config,
                forecast_run_id=run_id,
            )

            forecast_values: list[ForecastValue] = []
            for res in results:
                restaurant_uuid = uuid.UUID(res.restaurant_id)
                sku_uuid = uuid.UUID(res.sku_id)
                for date_str, p50, p10, p90 in zip(
                    res.forecast.dates,
                    res.forecast.p50,
                    res.forecast.p10,
                    res.forecast.p90,
                ):
                    forecast_values.append(
                        ForecastValue(
                            run_id=run_uuid,
                            restaurant_id=restaurant_uuid,
                            sku_id=sku_uuid,
                            forecast_date=pd.to_datetime(date_str).date(),
                            model_name=res.model_name,
                            quantity_p50=round(max(0.0, p50), 4),
                            quantity_p10=round(max(0.0, p10), 4),
                            quantity_p90=round(max(0.0, p90), 4),
                        )
                    )

            session.bulk_save_objects(forecast_values)
            session.execute(
                update(ForecastRun)
                .where(ForecastRun.id == run_uuid)
                .values(
                    status=RunStatus.complete,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

            logger.info(
                "Forecast run %s complete: %d series, %d values",
                run_id,
                len(results),
                len(forecast_values),
            )
            return {"run_id": run_id, "series": len(results), "values": len(forecast_values)}

        except Exception as exc:
            session.execute(
                update(ForecastRun)
                .where(ForecastRun.id == run_uuid)
                .values(
                    status=RunStatus.failed,
                    completed_at=datetime.now(timezone.utc),
                    error_message=str(exc)[:2000],
                )
            )
            session.commit()
            logger.exception("Forecast run %s failed: %s", run_id, exc)
            raise
