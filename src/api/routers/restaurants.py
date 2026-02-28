import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas.restaurants import RestaurantRead, SKURead
from src.db.models.restaurant import Restaurant, SKU

router = APIRouter()


@router.get("", response_model=list[RestaurantRead])
async def list_restaurants(db: AsyncSession = Depends(get_db)) -> list[Restaurant]:
    result = await db.execute(select(Restaurant).where(Restaurant.is_active.is_(True)))
    return list(result.scalars().all())


@router.get("/{restaurant_id}/skus", response_model=list[SKURead])
async def list_skus(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SKU]:
    # Verify restaurant exists
    res = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    result = await db.execute(select(SKU).where(SKU.is_active.is_(True)))
    return list(result.scalars().all())
