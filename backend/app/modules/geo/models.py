import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean, Time, Date, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    pickup_points = relationship("PickupPoint", back_populates="zone", cascade="all, delete-orphan", lazy="select")
    waves = relationship("Wave", back_populates="zone", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class PickupPoint(Base):
    __tablename__ = "pickup_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    lon: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    maps_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    zone = relationship("Zone", back_populates="pickup_points")
    waves = relationship("Wave", back_populates="pickup_point", lazy="select")
