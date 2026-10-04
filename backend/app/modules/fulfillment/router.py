from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.fulfillment.service import FulfillmentService
from app.modules.orders.service import OrderService
from app.modules.waves.service import WaveService
from app.modules.payments.models import Fulfillment as FulfillmentModel
from app.modules.payments.service import PaymentService
from app.modules.audit.service import write_audit
from app.core.outbox import emit

router = APIRouter(prefix="/admin", tags=["Admin: Fulfillment"])


@router.get("/waves/{wave_id}/assembly", response_model=list[dict])
async def get_assembly_sheet(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    shop, _ = shop_context
    items = await FulfillmentService.list_assembly_items(db, wave_id=_uuid.UUID(wave_id), shop_id=shop.id)
    return [
        {
            "id": str(i.id), "product_name": i.product_name,
            "variant_name": i.variant_name, "unit_short": i.unit_short,
            "required_qty": str(i.required_qty), "orders_count": i.orders_count,
            "status": i.status, "picked_qty": str(i.picked_qty),
            "packed_qty": str(i.packed_qty), "loaded_qty": str(i.loaded_qty),
        }
        for i in items
    ]


@router.patch("/assembly/{item_id}", response_model=dict)
async def update_assembly_item(
    item_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        item = await FulfillmentService.update_assembly_item(
            db, item_id=_uuid.UUID(item_id),
            wave_id=body.get("wave_id") and _uuid.UUID(body["wave_id"]),
            shop_id=shop.id,
            picked_qty=Decimal(str(body["picked_qty"])) if "picked_qty" in body else None,
            packed_qty=Decimal(str(body["packed_qty"])) if "packed_qty" in body else None,
            loaded_qty=Decimal(str(body["loaded_qty"])) if "loaded_qty" in body else None,
            created_by=member.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {
        "id": str(item.id), "status": item.status,
        "picked_qty": str(item.picked_qty), "packed_qty": str(item.packed_qty),
        "loaded_qty": str(item.loaded_qty),
    }


@router.get("/waves/{wave_id}/manifest", response_model=list[dict])
async def get_manifest(
    wave_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    shop, _ = shop_context
    wave_uuid = _uuid.UUID(wave_id)

    # Verify wave belongs to shop
    from app.modules.waves.models import Wave
    stmt = select(Wave).where(Wave.id == wave_uuid, Wave.shop_id == shop.id)
    res = await db.execute(stmt)
    wave = res.scalar_one_or_none()
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")

    manifest = await FulfillmentService.generate_manifest(db, wave_id=wave_uuid, shop_id=shop.id)
    return manifest


@router.post("/orders/{order_id}/deliver", response_model=dict)
async def deliver_order(
    order_id: str,
    body: dict = None,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    """Atomic delivery: scan QR → verify → accept cash if needed → mark delivered."""
    if body is None:
        body = {}
    shop, member = shop_context
    import uuid as _uuid
    order_uuid = _uuid.UUID(order_id)

    order = await OrderService.get_order(db, order_id=order_uuid, shop_id=shop.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get fulfillment
    from sqlalchemy import select
    stmt = select(FulfillmentModel).where(FulfillmentModel.order_id == order_uuid)
    res = await db.execute(stmt)
    fulfillment = res.scalar_one_or_none()
    if not fulfillment:
        raise HTTPException(status_code=404, detail="Fulfillment not found")

    if fulfillment.status not in ("ready", "out_for_delivery", "arrived"):
        raise HTTPException(status_code=400, detail=f"Cannot deliver: fulfillment status is {fulfillment.status}")

    # Accept cash payment if needed
    if body.get("accept_cash", False):
        pay_stmt = select(__import__('app.modules.payments.models', fromlist=['Payment']).Payment).where(
            __import__('app.modules.payments.models', fromlist=['Payment']).Payment.order_id == order_uuid
        )
        pay_res = await db.execute(pay_stmt)
        payment = pay_res.scalar_one_or_none()
        if payment and payment.method == "cash" and payment.status in ("unpaid", "pending"):
            await PaymentService.mark_paid(db, payment_id=payment.id, shop_id=shop.id, created_by=member.user_id)
            await db.flush()

    # Update fulfillment
    old_status = fulfillment.status
    if fulfillment.status == "delivered":
        # Already delivered — idempotent
        return {
            "id": str(order.id), "number": order.number,
            "order_status": order.order_status,
            "fulfillment_status": fulfillment.status,
            "delivered_at": fulfillment.delivered_at.isoformat(),
        }
    fulfillment.status = "delivered"
    fulfillment.delivered_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    from datetime import datetime as _dt
    fulfillment.updated_at = _dt.now(__import__('datetime').timezone.utc)

    # Update order status
    if order.order_status == "new":
        # First confirm, then complete
        try:
            await OrderService.transition_order_status(
                db, order_id=order_uuid, shop_id=shop.id,
                new_status="confirmed", created_by=member.user_id,
            )
        except ValueError:
            pass
    await OrderService.transition_order_status(
        db, order_id=order_uuid, shop_id=shop.id,
        new_status="completed", created_by=member.user_id,
    )
    await db.flush()

    # Audit + outbox
    await write_audit(
        db, shop_id=shop.id, actor_id=member.user_id,
        action="FULFILLMENT_DELIVER", entity_type="order", entity_id=order.id,
        before={"fulfillment_status": old_status},
        after={"fulfillment_status": "delivered", "order_status": "completed"},
    )
    await emit(
        db, shop_id=shop.id,
        event_type="fulfillment.delivered",
        aggregate_type="order", aggregate_id=order.id,
        payload={"order_id": str(order.id), "fulfillment_status": "delivered"},
    )

    await db.commit()
    return {
        "id": str(order.id), "number": order.number,
        "order_status": order.order_status,
        "fulfillment_status": fulfillment.status,
        "delivered_at": fulfillment.delivered_at.isoformat(),
    }


@router.post("/qr/scan", response_model=dict)
async def scan_qr(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    qr = body.get("qr_code", "").strip()
    if not qr:
        raise HTTPException(status_code=422, detail="qr_code is required")
    order = await OrderService.get_order_by_qr(db, qr_code=qr)
    if not order or order.shop_id != shop_context[0].id:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get payment status
    from sqlalchemy import select as _select
    from app.modules.payments.models import Payment as P
    pay_stmt = _select(P).where(P.order_id == order.id)
    pay_res = await db.execute(pay_stmt)
    payment = pay_res.scalar_one_or_none()

    # Get fulfillment status
    from app.modules.payments.models import Fulfillment as F
    ful_stmt = _select(F).where(F.order_id == order.id)
    ful_res = await db.execute(ful_stmt)
    fulfillment = ful_res.scalar_one_or_none()

    return {
        "id": str(order.id), "number": order.number,
        "status": order.order_status, "total": str(order.total),
        "currency": order.currency, "qr_code": order.qr_code,
        "payment_status": payment.status if payment else None,
        "payment_method": payment.method if payment else None,
        "fulfillment_status": fulfillment.status if fulfillment else None,
        "items": [{"name": i.product_name, "qty": str(i.qty)} for i in order.items],
    }
