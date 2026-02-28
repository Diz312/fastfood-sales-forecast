import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base, TimestampMixin


class DailySale(Base, TimestampMixin):
    __tablename__ = "daily_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skus.id"), nullable=False, index=True
    )
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("restaurant_id", "sku_id", "sale_date", name="uq_daily_sale"),
    )
