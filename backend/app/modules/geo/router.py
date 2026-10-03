import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.geo.models import Zone, PickupPoint
from app.modules.geo.service import ZoneService, PickupPointService

router = APIRouter(prefix="/admin/geo", tags=["Admin: Geo"])


# ─── Zones ────────────────────────────────────────────────────────────────────

@router.get("/zones", response_model=List[dict])
async def list_zones(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True),
):
    shop, _ = shop_context
    zones = await ZoneService.list(db, shop_id=shop.id, active_only=active_only)
    return [
        {"id": str(z.id), "name": z.name, "slug": z.slug, "is_active": z.is_active}
        for z in zones
    ]


@router.post("/zones", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_zone(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip()
    if not name or not slug:
        raise HTTPException(status_code=422, detail="name and slug are required")
    try:
        zone = await ZoneService.create(db, shop_id=shop.id, name=name, slug=slug, created_by=member.user_id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Zone with this slug already exists")
    await db.commit()
    return {"id": str(zone.id), "name": zone.name, "slug": zone.slug, "is_active": zone.is_active}


@router.get("/zones/{zone_id}", response_model=dict)
async def get_zone(
    zone_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    zone = await ZoneService.get(db, zone_id=_uuid.UUID(zone_id), shop_id=shop.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"id": str(zone.id), "name": zone.name, "slug": zone.slug, "is_active": zone.is_active}


@router.patch("/zones/{zone_id}", response_model=dict)
async def update_zone(
    zone_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    zone = await ZoneService.update(
        db, zone_id=_uuid.UUID(zone_id), shop_id=shop.id,
        name=body.get("name"), is_active=body.get("is_active"),
        created_by=member.user_id,
    )
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    await db.commit()
    return {"id": str(zone.id), "name": zone.name, "is_active": zone.is_active}


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    ok = await ZoneService.delete(db, zone_id=_uuid.UUID(zone_id), shop_id=shop.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Zone not found")
    await db.commit()


# ─── Pickup Points ────────────────────────────────────────────────────────────

@router.get("/zones/{zone_id}/pickup-points", response_model=List[dict])
async def list_pickup_points(
    zone_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    zone = await ZoneService.get(db, zone_id=_uuid.UUID(zone_id), shop_id=shop.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    points = await PickupPointService.list(db, shop_id=shop.id, zone_id=zone.id)
    return [
        {"id": str(p.id), "name": p.name, "address": p.address,
         "lat": float(p.lat) if p.lat else None, "lon": float(p.lon) if p.lon else None,
         "is_active": p.is_active}
        for p in points
    ]


@router.post("/zones/{zone_id}/pickup-points", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_pickup_point(
    zone_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    zone = await ZoneService.get(db, zone_id=_uuid.UUID(zone_id), shop_id=shop.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    from decimal import Decimal
    point = await PickupPointService.create(
        db, shop_id=shop.id, zone_id=zone.id, name=name,
        address=body.get("address"),
        lat=Decimal(str(body["lat"])) if body.get("lat") is not None else None,
        lon=Decimal(str(body["lon"])) if body.get("lon") is not None else None,
        maps_url=body.get("maps_url"),
        created_by=member.user_id,
    )
    await db.commit()
    return {"id": str(point.id), "name": point.name, "zone_id": str(zone.id)}


@router.patch("/pickup-points/{point_id}", response_model=dict)
async def update_pickup_point(
    point_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    point = await PickupPointService.update(
        db, point_id=_uuid.UUID(point_id), shop_id=shop.id,
        name=body.get("name"), address=body.get("address"),
        is_active=body.get("is_active"), created_by=member.user_id,
    )
    if not point:
        raise HTTPException(status_code=404, detail="Pickup point not found")
    await db.commit()
    return {"id": str(point.id), "name": point.name, "is_active": point.is_active}


@router.delete("/pickup-points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pickup_point(
    point_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    ok = await PickupPointService.delete(db, point_id=_uuid.UUID(point_id), shop_id=shop.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Pickup point not found")
    await db.commit()
