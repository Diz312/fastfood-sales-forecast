import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas.sales import DailySaleRead
from src.db.models.restaurant import Restaurant
from src.db.models.sales import DailySale

router = APIRouter()


@router.get("/{restaurant_id}/sales", response_model=list[DailySaleRead])
async def get_sales(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DailySale]:
    res = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    result = await db.execute(
        select(DailySale)
        .where(DailySale.restaurant_id == restaurant_id)
        .order_by(DailySale.sku_id, DailySale.sale_date)
    )
    return list(result.scalars().all())
