import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.schemas.forecasts import ForecastRunCreate, ForecastRunRead, ForecastValueRead
from src.db.models.forecast import ForecastRun, ForecastValue

router = APIRouter()


@router.post("", response_model=ForecastRunRead, status_code=201)
async def create_forecast_run(
    body: ForecastRunCreate,
    db: AsyncSession = Depends(get_db),
) -> ForecastRun:
    from src.workers.tasks.training import run_forecast_pipeline

    run = ForecastRun(triggered_by=body.triggered_by, config=body.config)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_forecast_pipeline.delay(str(run.id))
    return run


@router.get("/{run_id}", response_model=ForecastRunRead)
async def get_forecast_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ForecastRun:
    result = await db.execute(select(ForecastRun).where(ForecastRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    return run


@router.get("/{run_id}/values", response_model=list[ForecastValueRead])
async def get_forecast_values(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ForecastValue]:
    result = await db.execute(
        select(ForecastValue)
        .where(ForecastValue.run_id == run_id)
        .order_by(ForecastValue.sku_id, ForecastValue.forecast_date)
    )
    return list(result.scalars().all())
