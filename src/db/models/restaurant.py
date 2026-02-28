import uuid
from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, TimestampMixin


class ProductGroup(Base, TimestampMixin):
    __tablename__ = "product_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    skus: Mapped[list["SKU"]] = relationship("SKU", back_populates="product_group")


class SKU(Base, TimestampMixin):
    __tablename__ = "skus"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product_group: Mapped[ProductGroup] = relationship(
        "ProductGroup", back_populates="skus", foreign_keys=[product_group_id]
    )


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
