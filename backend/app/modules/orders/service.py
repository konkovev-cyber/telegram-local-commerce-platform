import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.outbox import emit
from app.modules.audit.service import write_audit
from app.modules.orders.models import Order, OrderItem


class OrderService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        items: List[Dict] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Order:
        if items is None:
            items = []

        # Idempotency: return existing order if key matches
        if idempotency_key:
            stmt = select(Order).where(Order.idempotency_key == idempotency_key)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        # Generate order number
        stmt = select(Order).where(
            Order.shop_id == shop_id
        ).order_by(Order.number.desc()).limit(1)
        res = await session.execute(stmt)
        last_order = res.scalar_one_or_none()
        number = (last_order.number + 1) if last_order else 1

        order = Order(
            id=uuid.uuid4(),
            shop_id=shop_id,
            customer_id=customer_id,
            number=number,
            idempotency_key=idempotency_key,
            notes=notes,
        )
        session.add(order)
        await session.flush()

        subtotal = Decimal("0")
        for item_data in items:
            product_id = item_data.get("product_id")
            variant_id = item_data.get("variant_id")
            qty = Decimal(str(item_data.get("qty", "1")))

            # Fetch product name and price snapshot
            from app.modules.catalog.service import CatalogService
            from app.modules.catalog.price_service import PriceService
            product = await CatalogService.get_product(session, product_id=product_id, shop_id=shop_id)
            if not product:
                raise ValueError(f"Product {product_id} not found in shop {shop_id}")

            name = product.name
            variant_name = None
            sku = product.sku
            if variant_id:
                variant = await session.execute(
                    select(__import__('app.modules.catalog.models', fromlist=['ProductVariant']).ProductVariant)
                    .where(
                        __import__('app.modules.catalog.models', fromlist=['ProductVariant']).ProductVariant.id == variant_id,
                        __import__('app.modules.catalog.models', fromlist=['ProductVariant']).ProductVariant.shop_id == shop_id
                    )
                )
                v = variant.scalar_one_or_none()
                if v:
                    variant_name = v.name
                    sku = v.sku or sku

            price_result = await PriceService.get_active_price(session, product_id=product_id, variant_id=variant_id)
            unit_price = price_result.amount if price_result else Decimal("0")

            item_subtotal = qty * unit_price
            subtotal += item_subtotal

            order_item = OrderItem(
                id=uuid.uuid4(),
                order_id=order.id,
                product_id=product_id,
                variant_id=variant_id,
                product_name=name,
                variant_name=variant_name,
                sku=sku,
                qty=qty,
                unit_price=unit_price,
                subtotal=item_subtotal,
            )
            session.add(order_item)

        order.subtotal = subtotal
        order.total = subtotal
        await session.flush()

        # INV-010: emit outbox event in the same transaction
        await emit(
            session,
            shop_id=shop_id,
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={"order_id": str(order.id), "number": order.number, "total": str(order.total)},
        )

        # INV-011: audit log
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ORDER_CREATED", entity_type="order", entity_id=order.id,
            after={"number": order.number, "total": str(order.total), "status": order.order_status},
        )

        return order

    @staticmethod
    async def list_orders(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> List[Order]:
        stmt = select(Order).where(Order.shop_id == shop_id)
        if status:
            stmt = stmt.where(Order.order_status == status)
        stmt = stmt.order_by(Order.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_order(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Order]:
        stmt = select(Order).where(Order.id == order_id, Order.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
