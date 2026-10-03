"""
PriceService — INV-005 compliant price history management.

Rules:
  - Active price: valid_to IS NULL
  - On set_price: close current (valid_to = now), insert new record
  - NEVER delete price rows — history is immutable
  - INV-011: audit_log written in the SAME transaction
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.price_models import Price
from app.modules.audit.service import write_audit


class PriceService:

    @staticmethod
    async def _get_active_price(
        session: AsyncSession,
        *,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID] = None,
    ) -> Optional[Price]:
        """
        Return the single active price row (valid_to IS NULL).
        Uses the partial index idx_prices_active.
        """
        stmt = select(Price).where(
            Price.product_id == product_id,
            Price.variant_id == variant_id,
            Price.valid_to.is_(None),
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def set_price(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID] = None,
        amount: Decimal,
        currency: str = "RUB",
        created_by: Optional[uuid.UUID] = None,
    ) -> Price:
        """
        INV-005: close current active price, write new row.
        INV-011: audit written in same transaction.
        """
        now = datetime.now(timezone.utc)

        # 1. Close existing active price (do NOT delete)
        current = await PriceService._get_active_price(
            session, product_id=product_id, variant_id=variant_id
        )
        before: Optional[dict] = None
        if current:
            current.valid_to = now
            before = {"amount": str(current.amount), "currency": current.currency}

        # 2. Insert new active price
        new_price = Price(
            id=uuid.uuid4(),
            shop_id=shop_id,
            product_id=product_id,
            variant_id=variant_id,
            amount=amount,
            currency=currency,
            valid_from=now,
            valid_to=None,
            created_by=created_by,
        )
        session.add(new_price)

        # 3. Audit — INV-011 same transaction
        await write_audit(
            session,
            shop_id=shop_id,
            actor_id=created_by,
            action="product.price_change",
            entity_type="price",
            entity_id=product_id,
            before=before,
            after={"amount": str(amount), "currency": currency},
        )

        await session.flush()
        return new_price

    @staticmethod
    async def get_active_price(
        session: AsyncSession,
        *,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID] = None,
    ) -> Optional[Price]:
        """Public read: current active price."""
        return await PriceService._get_active_price(
            session, product_id=product_id, variant_id=variant_id
        )

    @staticmethod
    async def get_price_history(
        session: AsyncSession,
        *,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID] = None,
    ) -> list[Price]:
        """Return all price rows for audit/history, newest first."""
        stmt = (
            select(Price)
            .where(
                Price.product_id == product_id,
                Price.variant_id == variant_id,
            )
            .order_by(Price.valid_from.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
