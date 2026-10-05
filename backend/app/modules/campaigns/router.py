import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.campaigns.models import Campaign, CampaignSource
from app.modules.campaigns.service import CampaignService, AnalyticsService

router = APIRouter(prefix="/admin/campaigns", tags=["Admin: Campaigns"])
analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ─── Campaigns CRUD ──────────────────────────────────────────────────────────

@router.get("", response_model=List[dict])
async def list_campaigns(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(False),
):
    shop, _ = shop_context
    campaigns = await CampaignService.list(db, shop_id=shop.id, active_only=active_only)
    return [
        {
            "id": str(c.id), "name": c.name, "is_active": c.is_active,
            "starts_at": c.starts_at.isoformat() if c.starts_at else None,
            "ends_at": c.ends_at.isoformat() if c.ends_at else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in campaigns
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_campaign(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    campaign = await CampaignService.create(
        db, shop_id=shop.id, name=name,
        starts_at=datetime.fromisoformat(body["starts_at"]) if body.get("starts_at") else None,
        ends_at=datetime.fromisoformat(body["ends_at"]) if body.get("ends_at") else None,
        is_active=body.get("is_active", True),
    )
    await db.commit()
    return {
        "id": str(campaign.id), "name": campaign.name,
        "is_active": campaign.is_active,
    }


@router.get("/{campaign_id}", response_model=dict)
async def get_campaign(
    campaign_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    campaign = await CampaignService.get(db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    sources = await CampaignService.list_sources(db, campaign_id=campaign.id, shop_id=shop.id)
    return {
        "id": str(campaign.id), "name": campaign.name,
        "is_active": campaign.is_active,
        "starts_at": campaign.starts_at.isoformat() if campaign.starts_at else None,
        "ends_at": campaign.ends_at.isoformat() if campaign.ends_at else None,
        "sources": [
            {
                "id": str(s.id), "name": s.name, "ref_code": s.ref_code,
                "deep_link": s.deep_link, "zone_id": str(s.zone_id) if s.zone_id else None,
                "clicks": s.clicks, "opens": s.opens, "carts": s.carts,
                "orders": s.orders, "revenue": float(s.revenue),
            }
            for s in sources
        ],
    }


@router.patch("/{campaign_id}", response_model=dict)
async def update_campaign(
    campaign_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    campaign = await CampaignService.update(
        db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id,
        name=body.get("name"), is_active=body.get("is_active"),
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.commit()
    return {"id": str(campaign.id), "name": campaign.name, "is_active": campaign.is_active}


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    campaign = await CampaignService.get(db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.delete(campaign)
    await db.commit()


# ─── Campaign Sources ────────────────────────────────────────────────────────

@router.post("/{campaign_id}/sources", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_source(
    campaign_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    campaign = await CampaignService.get(db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    name = body.get("name", "").strip()
    ref_code = body.get("ref_code", "").strip()
    if not name or not ref_code:
        raise HTTPException(status_code=422, detail="name and ref_code are required")

    zone_id = None
    if body.get("zone_id"):
        try:
            zone_id = _uuid.UUID(body["zone_id"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid zone_id")

    try:
        source = await CampaignService.create_source(
            db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id,
            name=name, ref_code=ref_code, zone_id=zone_id,
        )
        await db.commit()
        return {
            "id": str(source.id), "name": source.name,
            "ref_code": source.ref_code, "deep_link": source.deep_link,
        }
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="ref_code already exists")


@router.get("/{campaign_id}/funnel", response_model=List[dict])
async def get_funnel(
    campaign_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    shop, _ = shop_context
    import uuid as _uuid
    campaign = await CampaignService.get(db, campaign_id=_uuid.UUID(campaign_id), shop_id=shop.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    funnel = await AnalyticsService.get_funnel(
        db, shop_id=shop.id, campaign_id=_uuid.UUID(campaign_id), days=days,
    )
    return funnel


# ─── Analytics endpoints ─────────────────────────────────────────────────────

@analytics_router.post("/session", response_model=dict)
async def create_session(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Initialize or restore an analytics session (Mini App)."""
    import uuid as _uuid
    from app.modules.auth.models import User

    customer_id = None
    ref_code = body.get("ref_code")
    utm_source = body.get("utm_source")
    utm_medium = body.get("utm_medium")
    utm_campaign = body.get("utm_campaign")
    platform = body.get("platform", "desktop")

    # Resolve campaign source from ref_code
    campaign_source_id = None
    if ref_code:
        source = await CampaignService.resolve_ref_code(db, ref_code=ref_code)
        if source:
            campaign_source_id = source.id
            shop_id = None
            from app.modules.campaigns.models import Campaign as C
            from sqlalchemy import select as _select
            c_stmt = _select(C.shop_id).where(C.id == source.campaign_id)
            c_res = await db.execute(c_stmt)
            shop_id = c_res.scalar_one_or_none()
        else:
            shop_id = None
    else:
        shop_id = None

    # Get customer from JWT (if available via header)
    # For now, accept customer_id in body for testability
    if body.get("customer_id"):
        try:
            customer_id = _uuid.UUID(body["customer_id"])
        except ValueError:
            pass

    session = await AnalyticsService.create_or_get_session(
        db, shop_id=shop_id, customer_id=customer_id,
        campaign_source_id=campaign_source_id, ref_code=ref_code,
        utm_source=utm_source, utm_medium=utm_medium,
        utm_campaign=utm_campaign, platform=platform,
    )
    await db.commit()
    return {"id": str(session.id), "ref_code": session.ref_code}


@analytics_router.post("/event", status_code=status.HTTP_204_NO_CONTENT)
async def track_event(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Track an analytics event."""
    import uuid as _uuid
    event_name = body.get("event_name", "").strip()
    if not event_name:
        raise HTTPException(status_code=422, detail="event_name is required")

    session_id = None
    campaign_source_id = None
    customer_id = None
    entity_type = body.get("entity_type")
    entity_id = None
    metadata = body.get("metadata", {})
    shop_id = body.get("shop_id")

    if not shop_id:
        raise HTTPException(status_code=422, detail="shop_id is required")

    try:
        shop_id = _uuid.UUID(shop_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shop_id")

    if body.get("session_id"):
        try:
            session_id = _uuid.UUID(body["session_id"])
        except ValueError:
            pass

    if body.get("campaign_source_id"):
        try:
            campaign_source_id = _uuid.UUID(body["campaign_source_id"])
        except ValueError:
            pass

    if body.get("customer_id"):
        try:
            customer_id = _uuid.UUID(body["customer_id"])
        except ValueError:
            pass

    if entity_id:
        try:
            entity_id = _uuid.UUID(entity_id)
        except ValueError:
            pass

    await AnalyticsService.track_event(
        db, shop_id=shop_id, event_name=event_name,
        customer_id=customer_id, session_id=session_id,
        campaign_source_id=campaign_source_id,
        entity_type=entity_type, entity_id=entity_id,
        metadata=metadata,
    )
    await db.commit()
