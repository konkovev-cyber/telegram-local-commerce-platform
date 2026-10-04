import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AssemblyItem(Base):
    __tablename__ = "assembly_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id"),
        nullable=True,
    )
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    variant_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_short: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    required_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    picked_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    packed_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    loaded_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'picking', 'packed', 'loaded')",
            name="ck_assembly_items_status",
        ),
    )
