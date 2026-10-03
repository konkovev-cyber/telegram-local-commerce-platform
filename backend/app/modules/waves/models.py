import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Integer, Time, Date, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Wave(Base):
    __tablename__ = "waves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pickup_point_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pickup_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    opens_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_from: Mapped[time] = mapped_column(Time, nullable=False)
    delivery_to: Mapped[time] = mapped_column(Time, nullable=False)
    capacity_orders: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_orders: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="collecting",
        server_default="collecting",
    )
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    paid_online: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    paid_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    zone = relationship("Zone", back_populates="waves")
    pickup_point = relationship("PickupPoint", back_populates="waves")
    time_slots = relationship("WaveTimeSlot", back_populates="wave", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        CheckConstraint(
            "status IN ('collecting', 'closed', 'assembling', 'delivering', 'done', 'cancelled')",
            name="ck_waves_status",
        ),
    )


class WaveTimeSlot(Base):
    __tablename__ = "wave_time_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_time: Mapped[time] = mapped_column(Time, nullable=False)
    to_time: Mapped[time] = mapped_column(Time, nullable=False)
    max_orders: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    wave = relationship("Wave", back_populates="time_slots")
