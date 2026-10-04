import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context, get_current_user
from app.modules.orders.models import Order
from app.modules.orders.service import (
    OrderService, OrderCreateError, WaveNotCollectingError,
)

router = APIRouter(prefix="/admin/orders", tags=["Admin: Orders"])
customer_router = APIRouter(prefix="/orders", tags=["Customer: Orders"])


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=List[dict])
async def list_orders(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None),
    wave_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    shop, _ = shop_context
    w_id = uuid.UUID(wave_id) if wave_id else None
    orders = await OrderService.list_orders(db, shop_id=shop.id, status=status_filter, wave_id=w_id, limit=limit)
    return [
        {
            "id": str(o.id), "number": o.number, "status": o.order_status,
            "total": str(o.total), "currency": o.currency,
            "wave_id": str(o.wave_id) if o.wave_id else None,
            "qr_code": o.qr_code,
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


@router.get("/{order_id}", response_model=dict)
async def get_order(
    order_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    order = await OrderService.get_order(db, order_id=_uuid.UUID(order_id), shop_id=shop.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": str(order.id), "number": order.number, "status": order.order_status,
        "total": str(order.total), "subtotal": str(order.subtotal),
        "discount_amount": str(order.discount_amount), "currency": order.currency,
        "wave_id": str(order.wave_id) if order.wave_id else None,
        "qr_code": order.qr_code,
        "items": [{"product_name": i.product_name, "qty": str(i.qty),
                   "unit_price": str(i.unit_price), "subtotal": str(i.subtotal)}
                  for i in order.items],
        "created_at": order.created_at.isoformat(),
    }


@router.post("/{order_id}/status", response_model=dict)
async def change_order_status(
    order_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        order = await OrderService.transition_order_status(
            db, order_id=_uuid.UUID(order_id), shop_id=shop.id,
            new_status=body["status"], created_by=member.user_id,
            note=body.get("note"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"id": str(order.id), "status": order.order_status}


@router.post("/{order_id}/cancel", response_model=dict)
async def cancel_order(
    order_id: str,
    body: dict = None,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    if body is None:
        body = {}
    import uuid as _uuid
    try:
        order = await OrderService.cancel_order(db, order_id=_uuid.UUID(order_id),
                                                 shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"id": str(order.id), "status": order.order_status}


@router.patch("/{order_id}/fulfillment-status", response_model=dict)
async def update_fulfillment_status(
    order_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    from app.modules.payments.models import Fulfillment
    from sqlalchemy import select as _select
    from datetime import datetime as _dt, timezone as _tz

    order_uuid = _uuid.UUID(order_id)
    new_status = body.get("status", "")

    # Validate status transition
    valid_transitions = {
        "unfulfilled": {"assembling", "ready", "out_for_delivery", "arrived", "delivered"},
        "assembling": {"ready", "assembling"},
        "ready": {"out_for_delivery", "ready"},
        "out_for_delivery": {"arrived", "out_for_delivery"},
        "arrived": {"delivered", "arrived"},
        "delivered": set(),
    }
    if new_status not in valid_transitions:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    stmt = _select(Fulfillment).where(Fulfillment.order_id == order_uuid)
    res = await db.execute(stmt)
    fulfillment = res.scalar_one_or_none()
    if not fulfillment:
        # Create fulfillment if doesn't exist
        fulfillment = Fulfillment(
            id=_uuid.uuid4(),
            order_id=order_uuid,
            status="unfulfilled",
        )
        db.add(fulfillment)
        await db.flush()

    old_status = fulfillment.status
    if new_status not in valid_transitions.get(old_status, set()):
        raise HTTPException(status_code=400, detail=f"Invalid transition: {old_status} → {new_status}")

    fulfillment.status = new_status
    if new_status == "delivered":
        fulfillment.delivered_at = _dt.now(_tz.utc)
    fulfillment.updated_at = _dt.now(_tz.utc)

    await db.commit()
    return {"id": str(order_uuid), "fulfillment_status": fulfillment.status}


@router.get("/{order_id}/status-log", response_model=List[dict])
async def get_status_log(
    order_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    order = await OrderService.get_order(db, order_id=_uuid.UUID(order_id), shop_id=shop.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return [
        {"field": l.field, "old_value": l.old_value, "new_value": l.new_value,
         "created_at": l.created_at.isoformat()}
        for l in order.status_log
    ]


@router.post("/qr/scan", response_model=dict)
async def scan_qr(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    qr = body.get("qr_code", "").strip()
    if not qr:
        raise HTTPException(status_code=422, detail="qr_code is required")
    order = await OrderService.get_order_by_qr(db, qr_code=qr)
    if not order or order.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": str(order.id), "number": order.number, "status": order.order_status,
        "total": str(order.total), "qr_code": order.qr_code,
    }


# ─── Customer (Mini App) endpoints ────────────────────────────────────────────

@customer_router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_order(
    body: dict,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Create an order for the current customer."""
    try:
        order = await OrderService.create(
            db,
            shop_id=uuid.UUID(body["shop_id"]),
            customer_id=None,
            wave_id=uuid.UUID(body["wave_id"]) if body.get("wave_id") else None,
            zone_id=uuid.UUID(body["zone_id"]) if body.get("zone_id") else None,
            pickup_point_id=uuid.UUID(body["pickup_point_id"]) if body.get("pickup_point_id") else None,
            time_slot_id=uuid.UUID(body["time_slot_id"]) if body.get("time_slot_id") else None,
            items=body.get("items", []),
            idempotency_key=idempotency_key,
            discount_amount=Decimal(str(body.get("discount_amount", "0"))),
            notes=body.get("notes"),
            current_user=current_user,
        )
    except WaveNotCollectingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OrderCreateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "id": str(order.id), "number": order.number,
        "status": order.order_status, "total": str(order.total),
        "qr_code": order.qr_code,
    }


@customer_router.get("/my", response_model=List[dict])
async def list_my_orders(
    shop_id: str = Query(...),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    shop_uuid = _uuid.UUID(shop_id)
    customer_id = await OrderService.get_customer_id_for_user(db, user_id=current_user.id, shop_id=shop_uuid)
    if not customer_id:
        # No customer yet — return empty
        return []
    orders = await OrderService.list_customer_orders(
        db, customer_id=customer_id, shop_id=shop_uuid)
    return [
        {"id": str(o.id), "number": o.number, "status": o.order_status,
         "total": str(o.total), "qr_code": o.qr_code,
         "created_at": o.created_at.isoformat()}
        for o in orders
    ]


@customer_router.get("/{order_id}", response_model=dict)
async def get_my_order(
    order_id: str,
    shop_id: str = Query(...),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    shop_uuid = _uuid.UUID(shop_id)
    customer_id = await OrderService.get_customer_id_for_user(db, user_id=current_user.id, shop_id=shop_uuid)
    if not customer_id:
        raise HTTPException(status_code=404, detail="Order not found")
    order = await OrderService.get_order(
        db, order_id=_uuid.UUID(order_id), shop_id=shop_uuid)
    if not order or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": str(order.id), "number": order.number,
        "status": order.order_status, "total": str(order.total),
        "qr_code": order.qr_code,
        "items": [{"product_name": i.product_name, "qty": str(i.qty),
                   "unit_price": str(i.unit_price), "subtotal": str(i.subtotal)}
                  for i in order.items],
    }


@customer_router.get("/{order_id}/qr", response_model=dict)
async def get_order_qr(
    order_id: str,
    shop_id: str = Query(...),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    shop_uuid = _uuid.UUID(shop_id)
    customer_id = await OrderService.get_customer_id_for_user(db, user_id=current_user.id, shop_id=shop_uuid)
    if not customer_id:
        raise HTTPException(status_code=404, detail="Order not found")
    order = await OrderService.get_order(
        db, order_id=_uuid.UUID(order_id), shop_id=shop_uuid)
    if not order or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"id": str(order.id), "qr_code": order.qr_code, "status": order.order_status}
