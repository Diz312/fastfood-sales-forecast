from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class RestaurantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    region: str | None
    timezone: str
    opened_on: date | None
    is_active: bool


class SKURead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    product_group_id: uuid.UUID
    is_active: bool
