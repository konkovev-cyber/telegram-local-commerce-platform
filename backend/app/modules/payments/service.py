import uuid
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError


from app.modules.payments.models import Payment, PaymentTransaction, Refund, WebhookEvent
from app.core.outbox import emit
from app.modules.audit.service import write_audit


VALID_PAYMENT_TRANSITIONS = {
    "unpaid": {"pending", "cancelled"},
    "pending": {"paid", "failed"},
    "paid": {"refunded", "partially_refunded"},
    "partially_paid": {"paid", "failed"},
    "failed": {"pending"},
    "refunded": set(),
    "partially_refunded": {"paid"},
}


class PaymentProviderError(Exception):
    pass


class BasePaymentProvider(ABC):
    """Abstract base for payment providers."""

    @abstractmethod
    async def create_payment(
        self, order_id: uuid.UUID, amount: Decimal, currency: str, idempotency_key: str,
    ) -> Dict[str, Any]:
        """Create a payment intent. Returns {provider_payment_id, payment_url or invoice_url}."""
        ...

    @abstractmethod
    async def verify_webhook(self, raw_body: bytes, signature: str) -> Dict[str, Any]:
        """Verify webhook signature. Returns parsed event data."""
        ...

    @abstractmethod
    async def refund(self, payment_id: str, amount: Decimal, reason: str) -> Dict[str, Any]:
        """Process refund via provider. Returns {provider_ref_id}."""
        ...


class CashProvider(BasePaymentProvider):
    """Cash payment — status set manually by admin."""

    NAME = "cash"

    async def create_payment(self, order_id, amount, currency, idempotency_key):
        return {"provider_payment_id": None, "payment_url": None}

    async def verify_webhook(self, raw_body, signature):
        raise PaymentProviderError("Cash provider has no webhook")

    async def refund(self, payment_id, amount, reason):
        raise PaymentProviderError("Cash refunds handled manually")


class YooKassaProvider(BasePaymentProvider):
    """YooKassa integration stub (no real API calls in MVP)."""

    NAME = "yookassa"

    async def create_payment(self, order_id, amount, currency, idempotency_key):
        # In real impl: call YooKassa API, return confirmation_url
        return {
            "provider_payment_id": f"yk_{uuid.uuid4().hex}",
            "payment_url": f"https://pay.yookassa.ru/inv/{uuid.uuid4().hex[:12]}",
        }

    async def verify_webhook(self, raw_body, signature):
        # In real impl: verify YooKassa signature
        data = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
        return data

    async def refund(self, payment_id, amount, reason):
        return {"provider_ref_id": f"yk_ref_{uuid.uuid4().hex}"}


class TelegramPaymentProvider(BasePaymentProvider):
    """Telegram Payments API stub."""

    NAME = "telegram"

    async def create_payment(self, order_id, amount, currency, idempotency_key):
        return {
            "provider_payment_id": f"tg_{uuid.uuid4().hex}",
            "invoice_url": f"https://t.me/platformbot/pay/{uuid.uuid4().hex[:12]}",
        }

    async def verify_webhook(self, raw_body, signature):
        data = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
        return data

    async def refund(self, payment_id, amount, reason):
        return {"provider_ref_id": f"tg_ref_{uuid.uuid4().hex}"}


class PaymentService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        order_id: uuid.UUID,
        method: str,
        amount: Decimal,
        currency: str = "RUB",
        idempotency_key: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Payment:
        if idempotency_key:
            stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        provider = PaymentService._get_provider(method)

        payment = Payment(
            id=uuid.uuid4(),
            shop_id=shop_id,
            order_id=order_id,
            method=method,
            amount=amount,
            currency=currency,
            status="unpaid",
            idempotency_key=idempotency_key,
        )
        session.add(payment)
        await session.flush()

        # Call provider to create payment intent
        try:
            intent = await provider.create_payment(order_id, amount, currency, idempotency_key or "")
            payment.provider_payment_id = intent.get("provider_payment_id")
            payment.status = "pending" if intent.get("payment_url") or intent.get("invoice_url") else "unpaid"
        except PaymentProviderError:
            pass  # Cash provider doesn't need async call

        await session.flush()

        # Log transaction
        tx = PaymentTransaction(
            id=uuid.uuid4(),
            payment_id=payment.id,
            type="charge",
            amount=amount,
            currency=currency,
            status="pending" if payment.status == "pending" else "success",
            provider_tx_id=payment.provider_payment_id,
        )
        session.add(tx)

        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="PAYMENT_CREATED", entity_type="payment", entity_id=payment.id,
            after={"method": method, "amount": str(amount), "status": payment.status},
        )

        await emit(
            session, shop_id=shop_id,
            event_type="payment.created",
            aggregate_type="payment", aggregate_id=payment.id,
            payload={"payment_id": str(payment.id), "order_id": str(order_id),
                     "amount": str(amount), "status": payment.status},
        )

        return payment

    @staticmethod
    async def mark_paid(
        session: AsyncSession,
        *,
        payment_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Payment:
        stmt = select(Payment).options(selectinload(Payment.transactions), selectinload(Payment.refunds)).where(Payment.id == payment_id, Payment.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")
        if payment.status not in ("unpaid", "pending"):
            raise ValueError(f"Cannot mark paid: current status is {payment.status}")

        old_status = payment.status
        payment.status = "paid"
        payment.paid_at = datetime.now(timezone.utc)
        from datetime import datetime as _dt
        payment.updated_at = _dt.now(timezone.utc)

        # Update transaction
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.payment_id == payment_id,
            PaymentTransaction.type == "charge",
        ).order_by(PaymentTransaction.created_at.desc()).limit(1)
        res = await session.execute(stmt)
        tx = res.scalar_one_or_none()
        if tx:
            tx.status = "success"

        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="PAYMENT_PAID", entity_type="payment", entity_id=payment_id,
            before={"status": old_status},
            after={"status": "paid", "paid_at": payment.paid_at.isoformat()},
        )

        await PaymentService._emit_payment_event(session, shop_id, payment, "payment.completed")
        await PaymentService._sync_order_payment_status(session, payment)

        return payment

    @staticmethod
    async def process_webhook(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        provider: str,
        provider_event_id: str,
        event_type: str,
        raw_body: Dict[str, Any],
    ) -> Optional[Payment]:
        """INV-007: save raw event, then process."""
        event = WebhookEvent(
            id=uuid.uuid4(),
            shop_id=shop_id,
            provider=provider,
            event_type=event_type,
            provider_event_id=provider_event_id,
            raw_body=raw_body,
            processed=False,
        )
        try:
            session.add(event)
            await session.flush()
        except IntegrityError:
            await session.rollback()
            # Duplicate webhook event — return existing payment if found
            from sqlalchemy import select as _select
            stmt = _select(WebhookEvent).where(
                WebhookEvent.provider == provider,
                WebhookEvent.provider_event_id == provider_event_id,
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing and existing.processed and existing.raw_body:
                pid = existing.raw_body.get("data", {}).get("object", {}).get("id")
                if pid:
                    try:
                        from app.modules.payments.models import Payment as P
                        p_stmt = _select(P).where(P.id == uuid.UUID(str(pid)), P.shop_id == shop_id)
                        p_res = await session.execute(p_stmt)
                        p = p_res.scalar_one_or_none()
                        if p:
                            return p
                    except Exception:
                        pass
            return None

        # Find related payment by provider_payment_id in raw body
        pid = raw_body.get("data", {}).get("object", {}).get("id") or raw_body.get("id")
        if not pid:
            pid = raw_body.get("payment_id")
        if not pid:
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            await session.flush()
            return None

        try:
            payment_uuid = uuid.UUID(str(pid))
        except (ValueError, AttributeError):
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            await session.flush()
            return None

        stmt = select(Payment).where(Payment.id == payment_uuid, Payment.shop_id == shop_id)
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()
        if not payment:
            event.error = "Payment not found"
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            await session.flush()
            return None

        # Process based on event type
        if event_type in ("payment.succeeded", "confirmed", "paid"):
            old_status = payment.status
            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
            from datetime import datetime as _dt
            payment.updated_at = _dt.now(timezone.utc)

            tx = PaymentTransaction(
                id=uuid.uuid4(), payment_id=payment.id, type="charge",
                amount=payment.amount, currency=payment.currency, status="success",
                provider_tx_id=provider_event_id,
            )
            session.add(tx)

            await write_audit(
                session, shop_id=shop_id, actor_id=None,
                action="PAYMENT_WEBHOOK_PAID", entity_type="payment", entity_id=payment.id,
                before={"status": old_status},
                after={"status": "paid"},
            )
            await PaymentService._emit_payment_event(session, shop_id, payment, "payment.completed")
            await PaymentService._sync_order_payment_status(session, payment)
        elif event_type in ("payment.failed", "canceled"):
            payment.status = "failed"
            from datetime import datetime as _dt
            payment.updated_at = _dt.now(timezone.utc)
            await PaymentService._emit_payment_event(session, shop_id, payment, "payment.failed")

        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        await session.flush()
        return payment

    @staticmethod
    async def refund(
        session: AsyncSession,
        *,
        payment_id: uuid.UUID,
        shop_id: uuid.UUID,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Refund:
        stmt = select(Payment).options(selectinload(Payment.transactions), selectinload(Payment.refunds)).where(Payment.id == payment_id, Payment.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")
        if payment.status not in ("paid", "partially_paid"):
            raise ValueError(f"Cannot refund payment with status: {payment.status}")

        refund_amount = amount or payment.amount
        if refund_amount > payment.amount:
            raise ValueError("Refund amount exceeds payment amount")

        provider = PaymentService._get_provider(payment.method)
        try:
            ref_result = await provider.refund(payment.provider_payment_id or str(payment_id), refund_amount, reason or "")
        except PaymentProviderError:
            ref_result = {"provider_ref_id": None}

        refund = Refund(
            id=uuid.uuid4(),
            payment_id=payment_id,
            amount=refund_amount,
            currency=payment.currency,
            reason=reason,
            status="completed",
            provider_ref_id=ref_result.get("provider_ref_id"),
            created_by=created_by,
        )
        session.add(refund)

        # Update payment status
        remaining = payment.amount - refund_amount
        if remaining <= Decimal("0.01"):
            payment.status = "refunded"
        else:
            if payment.status == "paid":
                payment.status = "partially_refunded"

        # Log transaction
        tx = PaymentTransaction(
            id=uuid.uuid4(), payment_id=payment_id, type="refund",
            amount=refund_amount, currency=payment.currency, status="success",
            provider_tx_id=ref_result.get("provider_ref_id"),
        )
        session.add(tx)

        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="PAYMENT_REFUNDED", entity_type="payment", entity_id=payment_id,
            after={"refund_amount": str(refund_amount), "status": payment.status},
        )

        await emit(
            session, shop_id=shop_id,
            event_type="payment.refunded",
            aggregate_type="payment", aggregate_id=payment_id,
            payload={"payment_id": str(payment_id), "refund_amount": str(refund_amount)},
        )

        await session.flush()
        return refund

    @staticmethod
    async def list_payments(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        status: Optional[str] = None,
        order_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[Payment]:
        stmt = select(Payment).options(selectinload(Payment.transactions), selectinload(Payment.refunds)).where(Payment.shop_id == shop_id)
        if status:
            stmt = stmt.where(Payment.status == status)
        if order_id:
            stmt = stmt.where(Payment.order_id == order_id)
        stmt = stmt.order_by(Payment.created_at.desc()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_payment(
        session: AsyncSession,
        *,
        payment_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Payment]:
        stmt = select(Payment).options(selectinload(Payment.transactions), selectinload(Payment.refunds)).where(Payment.id == payment_id, Payment.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    def _get_provider(method: str) -> BasePaymentProvider:
        providers = {
            "cash": CashProvider(),
            "yookassa": YooKassaProvider(),
            "telegram": TelegramPaymentProvider(),
        }
        provider = providers.get(method)
        if not provider:
            raise ValueError(f"Unknown payment method: {method}")
        return provider

    @staticmethod
    async def _emit_payment_event(session: AsyncSession, shop_id: uuid.UUID, payment: Payment, event_type: str):
        await emit(
            session, shop_id=shop_id,
            event_type=event_type,
            aggregate_type="payment", aggregate_id=payment.id,
            payload={"payment_id": str(payment.id), "order_id": str(payment.order_id),
                     "amount": str(payment.amount), "status": payment.status},
        )

    @staticmethod
    async def _sync_order_payment_status(session: AsyncSession, payment: Payment):
        """When payment is completed, update order if needed."""
        from app.modules.orders.service import OrderService
        try:
            await OrderService.transition_order_status(
                session, order_id=payment.order_id, shop_id=payment.shop_id,
                new_status="confirmed",
            )
        except ValueError:
            pass  # Order may already be in expected state
