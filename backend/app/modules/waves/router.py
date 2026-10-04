import logging
logger = logging.getLogger(__name__)
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.waves.models import Wave, WaveTimeSlot
from app.modules.waves.service import WaveService
from app.modules.geo.service import ZoneService

router = APIRouter(prefix="/admin/waves", tags=["Admin: Waves"])


@router.get("", response_model=List[dict])
async def list_waves(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    shop, _ = shop_context
    z_id = None
    if zone_id:
        try:
            z_id = uuid.UUID(zone_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid zone_id")
        zone = await ZoneService.get(db, zone_id=z_id, shop_id=shop.id)
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
    waves = await WaveService.list(db, shop_id=shop.id, status_filter=status_filter, zone_id=z_id, limit=limit)
    return [
        {
            "id": str(w.id), "number": w.number, "name": w.name,
            "status": w.status, "zone_id": str(w.zone_id),
            "pickup_point_id": str(w.pickup_point_id) if w.pickup_point_id else None,
            "delivery_date": w.delivery_date.isoformat(),
            "delivery_from": w.delivery_from.isoformat(),
            "delivery_to": w.delivery_to.isoformat(),
            "closes_at": w.closes_at.isoformat() if w.closes_at else None,
            "orders_count": w.orders_count, "capacity_orders": w.capacity_orders,
            "min_orders": w.min_orders,
            "revenue_total": str(w.revenue_total),
        }
        for w in waves
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_wave(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    from datetime import datetime as _dt, date as _date, time as _time
    zone_id = _uuid.UUID(body["zone_id"])
    zone = await ZoneService.get(db, zone_id=zone_id, shop_id=shop.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    pickup_point_id = None
    if body.get("pickup_point_id"):
        try:
            pickup_point_id = _uuid.UUID(body["pickup_point_id"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid pickup_point_id")

    closes_at = _dt.fromisoformat(body["closes_at"]) if body.get("closes_at") else None
    delivery_date = _date.fromisoformat(body["delivery_date"]) if body.get("delivery_date") else None
    delivery_from = _time.fromisoformat(body["delivery_from"]) if body.get("delivery_from") else None
    delivery_to = _time.fromisoformat(body["delivery_to"]) if body.get("delivery_to") else None

    wave = await WaveService.create(
        db, shop_id=shop.id, zone_id=zone_id,
        pickup_point_id=pickup_point_id,
        name=body.get("name"),
        opens_at=None,
        closes_at=closes_at,
        delivery_date=delivery_date,
        delivery_from=delivery_from,
        delivery_to=delivery_to,
        capacity_orders=body.get("capacity_orders"),
        min_orders=body.get("min_orders"),
        created_by=member.user_id,
    )
    await db.commit()
    return {"id": str(wave.id), "number": wave.number, "status": wave.status}


@router.get("/{wave_id}", response_model=dict)
async def get_wave(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    wave = await WaveService.get(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id)
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    return {
        "id": str(wave.id), "number": wave.number, "name": wave.name,
        "status": wave.status, "zone_id": str(wave.zone_id),
        "pickup_point_id": str(wave.pickup_point_id) if wave.pickup_point_id else None,
        "delivery_date": wave.delivery_date.isoformat(),
        "delivery_from": wave.delivery_from.isoformat(),
        "delivery_to": wave.delivery_to.isoformat(),
        "closes_at": wave.closes_at.isoformat() if wave.closes_at else None,
        "opens_at": wave.opens_at.isoformat() if wave.opens_at else None,
        "capacity_orders": wave.capacity_orders,
        "min_orders": wave.min_orders,
        "orders_count": wave.orders_count,
        "revenue_total": str(wave.revenue_total),
        "paid_online": str(wave.paid_online),
        "paid_cash": str(wave.paid_cash),
    }


@router.post("/{wave_id}/close", response_model=dict)
async def close_wave(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        wave = await WaveService.close(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")

    # Generate assembly sheet after close
    from app.modules.fulfillment.service import FulfillmentService
    try:
        await FulfillmentService.generate_assembly_sheet(db, wave_id=wave.id, shop_id=shop.id)
    except Exception as e:
        logger.warning(f"Failed to generate assembly sheet for wave {wave_id}: {e}")

    await db.commit()
    return {"id": str(wave.id), "status": wave.status, "orders_count": wave.orders_count}


@router.post("/{wave_id}/cancel", response_model=dict)
async def cancel_wave(
    wave_id: str,
    body: dict = None,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    if body is None:
        body = {}
    try:
        wave = await WaveService.cancel(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id,
                                         reason=body.get("reason"), created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    await db.commit()
    return {"id": str(wave.id), "status": wave.status}


@router.post("/{wave_id}/assemble", response_model=dict)
async def start_assembling(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        wave = await WaveService.advance_to_assembling(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    await db.commit()
    return {"id": str(wave.id), "status": wave.status}


@router.post("/{wave_id}/deliver", response_model=dict)
async def start_delivering(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        wave = await WaveService.advance_to_delivering(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    await db.commit()
    return {"id": str(wave.id), "status": wave.status}


@router.post("/{wave_id}/done", response_model=dict)
async def mark_done(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        wave = await WaveService.advance_to_done(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    await db.commit()
    return {"id": str(wave.id), "status": wave.status}


# ─── Time Slots ───────────────────────────────────────────────────────────────

@router.get("/{wave_id}/slots", response_model=List[dict])
async def list_time_slots(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    wave = await WaveService.get(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id)
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    slots = await WaveService.list_time_slots(db, wave_id=wave.id)
    return [
        {"id": str(s.id), "from_time": s.from_time.isoformat(),
         "to_time": s.to_time.isoformat(), "max_orders": s.max_orders}
        for s in slots
    ]


@router.post("/{wave_id}/slots", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_time_slot(
    wave_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    from datetime import time as _time
    wave = await WaveService.get(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id)
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    try:
        from_time = _time.fromisoformat(body["from_time"])
        to_time = _time.fromisoformat(body["to_time"])
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid time format: {e}")
    slot = await WaveService.create_time_slot(
        db, wave_id=wave.id, from_time=from_time, to_time=to_time,
        max_orders=body.get("max_orders"),
    )
    await db.commit()
    return {"id": str(slot.id), "from_time": slot.from_time.isoformat(), "to_time": slot.to_time.isoformat()}


@router.delete("/{wave_id}/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_slot(
    wave_id: str,
    slot_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    ok = await WaveService.delete_time_slot(db, slot_id=_uuid.UUID(slot_id), wave_id=_uuid.UUID(wave_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Time slot not found")
    await db.commit()
