"""Forecast trigger and retrieval tools."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.forecast import ForecastRun, ForecastValue


async def trigger_forecast(
    db: AsyncSession,
    horizon_days: int = 365,
    triggered_by: str = "agent",
) -> dict:
    """Create a ForecastRun and dispatch the Celery pipeline task."""
    from src.workers.tasks.training import run_forecast_pipeline

    run = ForecastRun(
        triggered_by=triggered_by,
        config={"horizon_days": horizon_days},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_forecast_pipeline.delay(str(run.id))

    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "triggered_by": run.triggered_by,
        "message": f"Forecast pipeline dispatched (horizon={horizon_days} days)",
    }


async def get_forecast_values(
    db: AsyncSession,
    run_id: str,
    sku_id: str | None = None,
) -> dict:
    """Get forecast values for a run, optionally filtered by SKU."""
    run_uuid = uuid.UUID(run_id)

    # Check run exists
    run_result = await db.execute(select(ForecastRun).where(ForecastRun.id == run_uuid))
    run = run_result.scalar_one_or_none()
    if run is None:
        return {"error": f"Run {run_id} not found"}

    query = select(ForecastValue).where(ForecastValue.run_id == run_uuid)
    if sku_id is not None:
        query = query.where(ForecastValue.sku_id == uuid.UUID(sku_id))
    query = query.order_by(ForecastValue.sku_id, ForecastValue.forecast_date)

    result = await db.execute(query)
    values = result.scalars().all()

    # Summarize — return head + stats, not all 1825 rows
    summary_by_sku: dict[str, dict] = {}
    for v in values:
        key = str(v.sku_id)
        if key not in summary_by_sku:
            summary_by_sku[key] = {
                "sku_id": key,
                "count": 0,
                "p50_mean": 0.0,
                "first_date": str(v.forecast_date),
                "last_date": str(v.forecast_date),
            }
        summary_by_sku[key]["count"] += 1
        summary_by_sku[key]["p50_mean"] += float(v.quantity_p50)
        summary_by_sku[key]["last_date"] = str(v.forecast_date)

    for stats in summary_by_sku.values():
        if stats["count"] > 0:
            stats["p50_mean"] = round(stats["p50_mean"] / stats["count"], 2)

    return {
        "run_id": run_id,
        "run_status": run.status.value,
        "total_values": len(values),
        "by_sku": list(summary_by_sku.values()),
    }
