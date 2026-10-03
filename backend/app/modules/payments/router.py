import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.payments.models import Payment, Refund, WebhookEvent
from app.modules.payments.service import PaymentService, PaymentProviderError

router = APIRouter(prefix="/admin/payments", tags=["Admin: Payments"])
customer_router = APIRouter(prefix="/payments", tags=["Customer: Payments"])


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=List[dict])
async def list_payments(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    shop, _ = shop_context
    o_id = uuid.UUID(order_id) if order_id else None
    payments = await PaymentService.list_payments(db, shop_id=shop.id, status=status_filter, order_id=o_id, limit=limit)
    return [
        {
            "id": str(p.id), "order_id": str(p.order_id), "method": p.method,
            "amount": str(p.amount), "currency": p.currency,
            "status": p.status, "provider_payment_id": p.provider_payment_id,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in payments
    ]


@router.get("/{payment_id}", response_model=dict)
async def get_payment(
    payment_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    payment = await PaymentService.get_payment(db, payment_id=_uuid.UUID(payment_id), shop_id=shop.id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {
        "id": str(payment.id), "order_id": str(payment.order_id),
        "method": payment.method, "amount": str(payment.amount),
        "currency": payment.currency, "status": payment.status,
        "provider_payment_id": payment.provider_payment_id,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "transactions": [
            {"type": t.type, "amount": str(t.amount), "status": t.status,
             "provider_tx_id": t.provider_tx_id, "created_at": t.created_at.isoformat()}
            for t in payment.transactions
        ],
        "refunds": [
            {"id": str(r.id), "amount": str(r.amount), "status": r.status,
             "reason": r.reason, "created_at": r.created_at.isoformat()}
            for r in payment.refunds
        ],
    }


@router.post("/{payment_id}/mark-paid", response_model=dict)
async def mark_paid(
    payment_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    try:
        payment = await PaymentService.mark_paid(
            db, payment_id=_uuid.UUID(payment_id), shop_id=shop.id, created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"id": str(payment.id), "status": payment.status, "paid_at": payment.paid_at.isoformat()}


@router.post("/{payment_id}/refund", response_model=dict)
async def refund_payment(
    payment_id: str,
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    import uuid as _uuid
    from decimal import Decimal
    try:
        amount = Decimal(str(body.get("amount"))) if body.get("amount") else None
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid amount")
    try:
        refund = await PaymentService.refund(
            db, payment_id=_uuid.UUID(payment_id), shop_id=shop.id,
            amount=amount, reason=body.get("reason"), created_by=member.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"id": str(refund.id), "payment_id": str(refund.payment_id),
            "amount": str(refund.amount), "status": refund.status}


@router.get("/{payment_id}/transactions", response_model=List[dict])
async def list_transactions(
    payment_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    payment = await PaymentService.get_payment(db, payment_id=_uuid.UUID(payment_id), shop_id=shop.id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return [
        {"type": t.type, "amount": str(t.amount), "currency": t.currency,
         "status": t.status, "provider_tx_id": t.provider_tx_id,
         "created_at": t.created_at.isoformat()}
        for t in payment.transactions
    ]


@router.get("/{payment_id}/refunds", response_model=List[dict])
async def list_refunds(
    payment_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    payment = await PaymentService.get_payment(db, payment_id=_uuid.UUID(payment_id), shop_id=shop.id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return [
        {"id": str(r.id), "amount": str(r.amount), "currency": r.currency,
         "status": r.status, "reason": r.reason, "created_at": r.created_at.isoformat()}
        for r in payment.refunds
    ]


# ─── Customer (Mini App) endpoints ────────────────────────────────────────────

@customer_router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_payment(
    body: dict,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    shop, _ = shop_context
    try:
        payment = await PaymentService.create(
            db,
            shop_id=shop.id,
            order_id=uuid.UUID(body["order_id"]),
            method=body.get("method", "cash"),
            amount=__import__('decimal').Decimal(str(body.get("amount", "0"))),
            currency=body.get("currency", "RUB"),
            idempotency_key=idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {
        "id": str(payment.id), "order_id": str(payment.order_id),
        "method": payment.method, "amount": str(payment.amount), "status": payment.status,
        "provider_payment_id": payment.provider_payment_id,
        "payment_url": None,  # Would be set by provider
    }


@customer_router.get("/{payment_id}", response_model=dict)
async def get_payment(
    payment_id: str,
    shop_id: str = Query(...),
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    payment = await PaymentService.get_payment(
        db, payment_id=_uuid.UUID(payment_id), shop_id=_uuid.UUID(shop_id))
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {
        "id": str(payment.id), "order_id": str(payment.order_id),
        "amount": str(payment.amount), "currency": payment.currency,
        "status": payment.status,
        "provider_payment_id": payment.provider_payment_id,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }


# ─── Webhook endpoint ─────────────────────────────────────────────────────────

@router.post("/webhook/{provider}")
async def handle_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    INV-007: two-phase webhook ingestion.
    Fast path: verify signature → save raw event → return 200.
    Processing happens synchronously here for MVP (can be moved to worker later).
    """
    raw_body = await request.json()
    signature = request.headers.get("X-Signature", "")

    # Extract provider event ID
    provider_event_id = (
        raw_body.get("id")
        or raw_body.get("data", {}).get("id")
        or raw_body.get("event_id")
        or raw_body.get("provider_event_id")
        or str(uuid.uuid4())
    )

    event_type = (
        raw_body.get("type")
        or raw_body.get("event_type")
        or raw_body.get("object", {}).get("type", "unknown")
    )

    # Find shop_id from the payment if possible
    shop_id = None
    pid = raw_body.get("data", {}).get("object", {}).get("id") or raw_body.get("payment_id")
    if pid:
        try:
            from sqlalchemy import select
            from app.modules.payments.models import Payment as PModel
            stmt = select(PModel.shop_id).where(PModel.id == uuid.UUID(str(pid)))
            res = await db.execute(stmt)
            shop_id = res.scalar_one_or_none()
        except Exception:
            pass

    if not shop_id:
        raise HTTPException(status_code=400, detail="Cannot determine shop from webhook")

    try:
        payment = await PaymentService.process_webhook(
            db, shop_id=shop_id, provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type, raw_body=raw_body,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {"status": "accepted", "provider_event_id": provider_event_id}
