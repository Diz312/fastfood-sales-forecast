"""
Seed script: generates 1 restaurant × 5 SKUs × 180 days of synthetic fast food sales.

Patterns included:
- Weekly seasonality: Fri/Sat peaks, Mon trough
- Annual seasonality: summer high, January low
- SKU-level multiplicative effects
- US holiday effects
- Gaussian noise (heteroscedastic)
"""

import asyncio
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

settings = get_settings()

# ── Synthetic data parameters ──────────────────────────────────────────────────

RESTAURANT = {
    "id": str(uuid.uuid4()),
    "code": "REST_001",
    "name": "Downtown Flagship",
    "region": "Northeast",
}

PRODUCT_GROUPS = [
    {"code": "BURGERS", "name": "Burgers"},
    {"code": "DRINKS", "name": "Drinks"},
]

SKUS = [
    {"code": "SKU_001", "name": "Classic Burger", "group": "BURGERS", "base_qty": 80, "price": 8.99},
    {"code": "SKU_002", "name": "Deluxe Burger", "group": "BURGERS", "base_qty": 50, "price": 11.99},
    {"code": "SKU_003", "name": "Cheeseburger", "group": "BURGERS", "base_qty": 65, "price": 9.49},
    {"code": "SKU_004", "name": "Cola Large", "group": "DRINKS", "base_qty": 120, "price": 2.99},
    {"code": "SKU_005", "name": "Milkshake", "group": "DRINKS", "base_qty": 30, "price": 4.99},
]

START_DATE = date(2024, 7, 1)  # 180 days back from ~Jan 2025
N_DAYS = 180

# US major holidays (simplified)
US_HOLIDAYS = {
    date(2024, 7, 4),    # Independence Day
    date(2024, 9, 2),    # Labor Day
    date(2024, 11, 28),  # Thanksgiving
    date(2024, 12, 25),  # Christmas
    date(2025, 1, 1),    # New Year's Day
}

# Day-of-week multipliers (Mon=0 ... Sun=6)
DOW_MULTIPLIERS = [0.72, 0.78, 0.85, 0.95, 1.18, 1.30, 1.22]


def generate_quantity(base_qty: float, sale_date: date, sku_noise_scale: float = 0.12) -> int:
    """Generate realistic daily quantity for a SKU."""
    # Day of week effect
    dow_mult = DOW_MULTIPLIERS[sale_date.weekday()]

    # Annual seasonality: sine wave peaking in July
    day_of_year = sale_date.timetuple().tm_yday
    seasonal_mult = 1.0 + 0.15 * np.sin(2 * np.pi * (day_of_year - 90) / 365)

    # Holiday effect
    holiday_mult = 0.55 if sale_date in US_HOLIDAYS else 1.0

    # Slight upward trend (0.5% per month)
    days_elapsed = (sale_date - START_DATE).days
    trend_mult = 1.0 + 0.005 * (days_elapsed / 30)

    # Multiplicative noise
    noise = np.random.lognormal(0, sku_noise_scale)

    qty = base_qty * dow_mult * seasonal_mult * holiday_mult * trend_mult * noise
    return max(0, int(round(qty)))


async def seed(session: AsyncSession) -> None:
    from sqlalchemy import text

    np.random.seed(42)

    log.info("Seeding product groups...")
    pg_ids: dict[str, str] = {}
    for pg in PRODUCT_GROUPS:
        pg_id = str(uuid.uuid4())
        pg_ids[pg["code"]] = pg_id
        await session.execute(
            text(
                "INSERT INTO product_groups (id, code, name) VALUES (:id, :code, :name) "
                "ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name RETURNING id"
            ),
            {"id": pg_id, "code": pg["code"], "name": pg["name"]},
        )

    log.info("Seeding restaurant...")
    rest_id = RESTAURANT["id"]
    await session.execute(
        text(
            "INSERT INTO restaurants (id, code, name, region) "
            "VALUES (:id, :code, :name, :region) ON CONFLICT (code) DO NOTHING"
        ),
        {"id": rest_id, "code": RESTAURANT["code"], "name": RESTAURANT["name"],
         "region": RESTAURANT["region"]},
    )

    log.info("Seeding SKUs...")
    sku_ids: dict[str, str] = {}
    for sku in SKUS:
        sku_id = str(uuid.uuid4())
        sku_ids[sku["code"]] = sku_id
        pg_id = pg_ids[sku["group"]]
        await session.execute(
            text(
                "INSERT INTO skus (id, code, name, product_group_id) "
                "VALUES (:id, :code, :name, :pg_id) ON CONFLICT (code) DO NOTHING"
            ),
            {"id": sku_id, "code": sku["code"], "name": sku["name"], "pg_id": pg_id},
        )

    log.info("Generating daily sales...", n_days=N_DAYS, n_skus=len(SKUS))
    rows = []
    for day_offset in range(N_DAYS):
        sale_date = START_DATE + timedelta(days=day_offset)
        for sku in SKUS:
            qty = generate_quantity(sku["base_qty"], sale_date)
            revenue = round(qty * sku["price"], 4)
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "restaurant_id": rest_id,
                    "sku_id": sku_ids[sku["code"]],
                    "sale_date": sale_date,
                    "quantity": qty,
                    "revenue": Decimal(str(revenue)),
                }
            )

    # Bulk insert in chunks
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        await session.execute(
            text(
                "INSERT INTO daily_sales (id, restaurant_id, sku_id, sale_date, quantity, revenue) "
                "VALUES (:id, :restaurant_id, :sku_id, :sale_date, :quantity, :revenue) "
                "ON CONFLICT (restaurant_id, sku_id, sale_date) DO NOTHING"
            ),
            chunk,
        )

    await session.commit()
    log.info(
        "Seed complete",
        total_rows=len(rows),
        restaurants=1,
        skus=len(SKUS),
        days=N_DAYS,
    )


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
