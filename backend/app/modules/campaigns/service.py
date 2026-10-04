import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, Numeric, case, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.models import Campaign, CampaignSource, AnalyticsSession, AnalyticsEvent


class CampaignService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        name: str,
        starts_at: Optional[datetime] = None,
        ends_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> Campaign:
        campaign = Campaign(
            id=uuid.uuid4(),
            shop_id=shop_id,
            name=name,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
        )
        session.add(campaign)
        await session.flush()
        return campaign

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        active_only: bool = False,
    ) -> List[Campaign]:
        stmt = select(Campaign).where(Campaign.shop_id == shop_id)
        if active_only:
            stmt = stmt.where(Campaign.is_active == True)
        stmt = stmt.order_by(Campaign.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get(
        session: AsyncSession,
        *,
        campaign_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Campaign]:
        stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def update(
        session: AsyncSession,
        *,
        campaign_id: uuid.UUID,
        shop_id: uuid.UUID,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Campaign]:
        stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.shop_id == shop_id)
        res = await session.execute(stmt)
        campaign = res.scalar_one_or_none()
        if not campaign:
            return None
        if name is not None:
            campaign.name = name
        if is_active is not None:
            campaign.is_active = is_active
        return campaign

    @staticmethod
    async def create_source(
        session: AsyncSession,
        *,
        campaign_id: uuid.UUID,
        shop_id: uuid.UUID,
        name: str,
        ref_code: str,
        zone_id: Optional[uuid.UUID] = None,
    ) -> CampaignSource:
        # Generate deep link
        from app.core.config import settings
        bot_username = settings.platform_bot_token.split(":")[0] if ":" in settings.platform_bot_token else "platformbot"
        deep_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"

        source = CampaignSource(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            zone_id=zone_id,
            name=name,
            ref_code=ref_code,
            deep_link=deep_link,
        )
        session.add(source)
        await session.flush()
        return source

    @staticmethod
    async def list_sources(
        session: AsyncSession,
        *,
        campaign_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> List[CampaignSource]:
        stmt = (
            select(CampaignSource)
            .join(Campaign, Campaign.id == CampaignSource.campaign_id)
            .where(CampaignSource.campaign_id == campaign_id, Campaign.shop_id == shop_id)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def resolve_ref_code(
        session: AsyncSession,
        *,
        ref_code: str,
        shop_id: Optional[uuid.UUID] = None,
    ) -> Optional[CampaignSource]:
        """Resolve a ref_code to its source, optionally filtered by shop."""
        stmt = select(CampaignSource).where(CampaignSource.ref_code == ref_code)
        if shop_id:
            stmt = stmt.join(Campaign, Campaign.id == CampaignSource.campaign_id).where(
                Campaign.shop_id == shop_id
            )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()


class AnalyticsService:
    @staticmethod
    async def create_or_get_session(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        campaign_source_id: Optional[uuid.UUID] = None,
        ref_code: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> AnalyticsSession:
        # Validate customer exists if provided
        if customer_id:
            from app.modules.auth.models import Customer as _C
            _check = await session.execute(select(_C.id).where(_C.id == customer_id))
            if _check.scalar_one_or_none() is None:
                customer_id = None

        # Try to find existing session by customer_id
        if customer_id:
            stmt = select(AnalyticsSession).where(
                AnalyticsSession.customer_id == customer_id,
                AnalyticsSession.shop_id == shop_id,
            ).order_by(AnalyticsSession.last_seen_at.desc()).limit(1)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                return existing

        # Create new session
        session_obj = AnalyticsSession(
            id=uuid.uuid4(),
            shop_id=shop_id,
            customer_id=customer_id,
            campaign_source_id=campaign_source_id,
            ref_code=ref_code,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            platform=platform,
        )
        session.add(session_obj)
        await session.flush()
        return session_obj

    @staticmethod
    async def track_event(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        event_name: str,
        customer_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
        campaign_source_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsEvent:
        if metadata is None:
            metadata = {}

        # Inherit campaign_source_id and customer_id from session if not provided
        if session_id:
            sess_stmt = select(AnalyticsSession).where(AnalyticsSession.id == session_id)
            sess_res = await session.execute(sess_stmt)
            sess = sess_res.scalar_one_or_none()
            if sess:
                if not campaign_source_id:
                    campaign_source_id = sess.campaign_source_id
                if not customer_id:
                    customer_id = sess.customer_id

        event = AnalyticsEvent(
            id=uuid.uuid4(),
            shop_id=shop_id,
            customer_id=customer_id,
            session_id=session_id,
            campaign_source_id=campaign_source_id,
            event_name=event_name,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=metadata,
        )
        session.add(event)
        await session.flush()

        # Update campaign source counters if applicable
        if campaign_source_id and event_name in ("campaign_click", "app_open", "add_to_cart", "order_created"):
            counter_map = {
                "campaign_click": "clicks",
                "app_open": "opens",
                "add_to_cart": "carts",
                "order_created": "orders",
            }
            col = counter_map.get(event_name)
            if col:
                stmt = select(CampaignSource).where(CampaignSource.id == campaign_source_id).with_for_update()
                res = await session.execute(stmt)
                source = res.scalar_one_or_none()
                if source:
                    current = getattr(source, col, 0)
                    setattr(source, col, current + 1)

        return event

    @staticmethod
    async def get_funnel(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        campaign_id: Optional[uuid.UUID] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Calculate conversion funnel for campaign sources."""
        from datetime import timedelta as _td

        cutoff = datetime.now(timezone.utc) - _td(days=days)

        subquery = (
            select(
                AnalyticsEvent.campaign_source_id,
                func.count().label("total_events"),
                func.count().filter(
                    AnalyticsEvent.event_name == "campaign_click"
                ).label("clicks"),
                func.count().filter(
                    AnalyticsEvent.event_name == "app_open"
                ).label("opens"),
                func.count().filter(
                    AnalyticsEvent.event_name == "add_to_cart"
                ).label("carts"),
                func.count().filter(
                    AnalyticsEvent.event_name == "order_created"
                ).label("orders"),
                func.sum(
                    case(
                        (AnalyticsEvent.event_name == "order_created",
                         cast(AnalyticsEvent.event_metadata.op("->>")("total"), Numeric(12, 2))),
                        else_=0
                    )
                ).label("revenue"),
            )
            .where(
                AnalyticsEvent.shop_id == shop_id,
                AnalyticsEvent.created_at >= cutoff,
            )
            .group_by(AnalyticsEvent.campaign_source_id)
            .subquery()
        )

        stmt = (
            select(
                CampaignSource.id,
                CampaignSource.name,
                CampaignSource.ref_code,
                subquery.c.clicks,
                subquery.c.opens,
                subquery.c.carts,
                subquery.c.orders,
                subquery.c.revenue,
            )
            .join(subquery, CampaignSource.id == subquery.c.campaign_source_id)
            .outerjoin(Campaign, Campaign.id == CampaignSource.campaign_id)
        )

        if campaign_id:
            stmt = stmt.where(CampaignSource.campaign_id == campaign_id)

        res = await session.execute(stmt)
        rows = res.fetchall()

        funnel = []
        for row in rows:
            cs_id, name, ref_code, clicks, opens, carts, orders, revenue = row
            funnel.append({
                "source_id": str(cs_id),
                "name": name,
                "ref_code": ref_code,
                "clicks": clicks or 0,
                "opens": opens or 0,
                "carts": carts or 0,
                "orders": orders or 0,
                "revenue": float(revenue or 0),
                "click_to_open_cr": round((opens or 0) / (clicks or 1) * 100, 1),
                "open_to_cart_cr": round((carts or 0) / (opens or 1) * 100, 1),
                "cart_to_order_cr": round((orders or 0) / (carts or 1) * 100, 1),
            })

        return sorted(funnel, key=lambda x: x["orders"], reverse=True)
