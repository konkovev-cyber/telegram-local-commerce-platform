import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, BigInteger, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    number: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False)
    order_status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    subtotal: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("order_status IN ('new', 'confirmed', 'cancelled', 'completed', 'no_show')", name="ck_orders_order_status"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    variant_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    qty: Mapped[Numeric] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
