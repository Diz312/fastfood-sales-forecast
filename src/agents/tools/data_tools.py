"""Deterministic data query tools for the orchestrator agent."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.restaurant import Restaurant, SKU
from src.db.models.sales import DailySale


async def get_sales_summary(db: AsyncSession) -> dict:
    """Return aggregate stats across all sales in the database."""
    count_result = await db.execute(select(func.count()).select_from(DailySale))
    total_rows = count_result.scalar_one()

    date_result = await db.execute(
        select(func.min(DailySale.sale_date), func.max(DailySale.sale_date))
    )
    min_date, max_date = date_result.one()

    qty_result = await db.execute(
        select(func.sum(DailySale.quantity), func.avg(DailySale.quantity))
    )
    total_qty, avg_qty = qty_result.one()

    rest_result = await db.execute(
        select(func.count()).select_from(Restaurant).where(Restaurant.is_active.is_(True))
    )
    n_restaurants = rest_result.scalar_one()

    sku_result = await db.execute(
        select(func.count()).select_from(SKU).where(SKU.is_active.is_(True))
    )
    n_skus = sku_result.scalar_one()

    return {
        "total_rows": total_rows,
        "date_range": {"min": str(min_date), "max": str(max_date)},
        "total_quantity": float(total_qty or 0),
        "avg_daily_quantity": round(float(avg_qty or 0), 2),
        "n_restaurants": n_restaurants,
        "n_skus": n_skus,
    }


async def get_series_stats(db: AsyncSession, restaurant_id: str, sku_id: str) -> dict:
    """Return per-series statistics for a specific restaurant/SKU pair."""
    import uuid

    rest_uuid = uuid.UUID(restaurant_id)
    sku_uuid = uuid.UUID(sku_id)

    result = await db.execute(
        select(
            func.count().label("n_days"),
            func.min(DailySale.sale_date).label("start_date"),
            func.max(DailySale.sale_date).label("end_date"),
            func.avg(DailySale.quantity).label("mean_qty"),
            func.stddev_pop(DailySale.quantity).label("std_qty"),
            func.min(DailySale.quantity).label("min_qty"),
            func.max(DailySale.quantity).label("max_qty"),
        ).where(
            DailySale.restaurant_id == rest_uuid,
            DailySale.sku_id == sku_uuid,
        )
    )
    row = result.one()

    return {
        "restaurant_id": restaurant_id,
        "sku_id": sku_id,
        "n_days": row.n_days,
        "start_date": str(row.start_date),
        "end_date": str(row.end_date),
        "mean_quantity": round(float(row.mean_qty or 0), 2),
        "std_quantity": round(float(row.std_qty or 0), 2),
        "min_quantity": int(row.min_qty or 0),
        "max_quantity": int(row.max_qty or 0),
    }
