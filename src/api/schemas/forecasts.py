from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


class ForecastRunCreate(BaseModel):
    triggered_by: str = "manual"
    config: dict[str, Any] = {}


class ForecastRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    triggered_by: str
    status: RunStatus
    config: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    celery_task_id: str | None
    created_at: datetime


class ForecastValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    restaurant_id: uuid.UUID
    sku_id: uuid.UUID
    forecast_date: date
    model_name: str
    quantity_p50: Decimal
    quantity_p10: Decimal | None
    quantity_p90: Decimal | None
    is_reconciled: bool
