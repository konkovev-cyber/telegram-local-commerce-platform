import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sources = relationship("CampaignSource", back_populates="campaign", cascade="all, delete-orphan", lazy="select")


class CampaignSource(Base):
    __tablename__ = "campaign_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ref_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    deep_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    carts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)

    campaign = relationship("Campaign", back_populates="sources")


class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    campaign_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    utm_source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ref_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    events = relationship("AnalyticsEvent", back_populates="session", cascade="all, delete-orphan", lazy="select")


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analytics_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    campaign_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_name: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, name="metadata")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    session = relationship("AnalyticsSession", back_populates="events")
