import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fulfillment.models import AssemblyItem
from app.modules.audit.service import write_audit


class FulfillmentService:
    @staticmethod
    async def generate_assembly_sheet(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> List[AssemblyItem]:
        """Generate assembly items from all non-cancelled orders in the wave."""
        from app.modules.orders.models import Order, OrderItem
        from app.modules.waves.models import Wave

        # Verify wave belongs to shop
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id)
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            raise ValueError(f"Wave {wave_id} not found in shop {shop_id}")

        # Aggregate order items by product+variant
        stmt = select(
            OrderItem.product_id,
            OrderItem.variant_id,
            func.sum(OrderItem.qty).label("total_qty"),
            func.count(Order.id).label("order_count"),
        ).join(
            Order, Order.id == OrderItem.order_id
        ).where(
            Order.wave_id == wave_id,
            Order.order_status != "cancelled",
        ).group_by(
            OrderItem.product_id, OrderItem.variant_id
        )
        res = await session.execute(stmt)
        rows = res.fetchall()

        items = []
        for row in rows:
            product_id, variant_id, total_qty, order_count = row
            item = AssemblyItem(
                id=uuid.uuid4(),
                wave_id=wave_id,
                product_id=product_id,
                variant_id=variant_id,
                product_name="",  # Filled below
                variant_name=None,
                unit_short=None,
                required_qty=total_qty,
                orders_count=order_count,
                status="pending",
            )
            session.add(item)
            items.append(item)

        await session.flush()

        # Fill snapshots from catalog (batch fetch to avoid lazy load)
        from app.modules.catalog.service import CatalogService
        from app.modules.catalog.models import Product, ProductVariant
        product_ids = [item.product_id for item in items]
        stmt = select(Product).where(Product.id.in_(product_ids), Product.shop_id == shop_id)
        res = await session.execute(stmt)
        products = {p.id: p for p in res.scalars().all()}
        
        variant_ids = [item.variant_id for item in items if item.variant_id]
        if variant_ids:
            v_stmt = select(ProductVariant).where(
                ProductVariant.id.in_(variant_ids),
                ProductVariant.shop_id == shop_id,
            )
            v_res = await session.execute(v_stmt)
            variants = {v.id: v for v in v_res.scalars().all()}
        else:
            variants = {}
        
        for item in items:
            product = products.get(item.product_id)
            if product:
                item.product_name = product.name
                if product.unit_id:
                    u_stmt = select(__import__('app.modules.catalog.models', fromlist=['Unit']).Unit).where(
                        __import__('app.modules.catalog.models', fromlist=['Unit']).Unit.id == product.unit_id,
                        __import__('app.modules.catalog.models', fromlist=['Unit']).Unit.shop_id == shop_id,
                    )
                    u_res = await session.execute(u_stmt)
                    unit = u_res.scalar_one_or_none()
                    if unit:
                        item.unit_short = unit.short_name
            if item.variant_id and item.variant_id in variants:
                item.variant_name = variants[item.variant_id].name

        return items

    @staticmethod
    async def update_assembly_item(
        session: AsyncSession,
        *,
        item_id: uuid.UUID,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        picked_qty: Optional[Decimal] = None,
        packed_qty: Optional[Decimal] = None,
        loaded_qty: Optional[Decimal] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> AssemblyItem:
        stmt = select(AssemblyItem).where(
            AssemblyItem.id == item_id,
            AssemblyItem.wave_id == wave_id,
        )
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ValueError("Assembly item not found")

        before = {
            "picked_qty": str(item.picked_qty),
            "packed_qty": str(item.packed_qty),
            "loaded_qty": str(item.loaded_qty),
            "status": item.status,
        }

        if picked_qty is not None:
            if picked_qty > item.required_qty:
                raise ValueError("Picked qty exceeds required qty")
            item.picked_qty = picked_qty
        if packed_qty is not None:
            if packed_qty > item.picked_qty:
                raise ValueError("Packed qty exceeds picked qty")
            item.packed_qty = packed_qty
        if loaded_qty is not None:
            if loaded_qty > item.packed_qty:
                raise ValueError("Loaded qty exceeds packed qty")
            item.loaded_qty = loaded_qty

        # Auto-update status
        if item.loaded_qty >= item.required_qty:
            item.status = "loaded"
        elif item.packed_qty >= item.required_qty:
            item.status = "packed"
        elif item.picked_qty > 0:
            item.status = "picking"

        from datetime import datetime as _dt
        item.updated_at = _dt.now(timezone.utc)

        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ASSEMBLY_ITEM_UPDATED", entity_type="assembly_item", entity_id=item_id,
            before=before,
            after={"status": item.status, "loaded_qty": str(item.loaded_qty)},
        )

        return item

    @staticmethod
    async def list_assembly_items(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> List[AssemblyItem]:
        stmt = select(AssemblyItem).where(
            AssemblyItem.wave_id == wave_id,
        ).order_by(AssemblyItem.product_name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def generate_manifest(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Generate pickup manifest grouped by time_slot and pickup_point."""
        from app.modules.orders.models import Order
        from app.modules.payments.models import Payment, Fulfillment
        from app.modules.auth.models import Customer
        from app.modules.waves.models import WaveTimeSlot
        from sqlalchemy import select as _select

        # Fetch orders with only needed columns (no relationships)
        stmt = _select(
            Order.id, Order.number, Order.customer_id, Order.time_slot_id,
            Order.total, Order.currency, Order.order_status,
        ).where(
            Order.wave_id == wave_id,
            Order.shop_id == shop_id,
            Order.order_status != "cancelled",
        ).order_by(Order.time_slot_id, Order.number)
        res = await session.execute(stmt)
        rows = res.fetchall()

        # Batch fetch payments
        order_ids = [r[0] for r in rows]
        if order_ids:
            pay_stmt = _select(Payment.order_id, Payment.method, Payment.status).where(
                Payment.order_id.in_(order_ids)
            )
            pay_res = await session.execute(pay_stmt)
            payments = {r[0]: {"method": r[1], "status": r[2]} for r in pay_res.fetchall()}
        else:
            payments = {}

        # Batch fetch fulfillments
        if order_ids:
            ful_stmt = _select(Fulfillment.order_id, Fulfillment.status).where(
                Fulfillment.order_id.in_(order_ids)
            )
            ful_res = await session.execute(ful_stmt)
            fulfillments = {r[0]: r[1] for r in ful_res.fetchall()}
        else:
            fulfillments = {}

        # Batch fetch customers
        cust_ids = [r[2] for r in rows if r[2]]
        if cust_ids:
            cust_stmt = _select(Customer.id, Customer.display_name, Customer.phone).where(
                Customer.id.in_(cust_ids)
            )
            cust_res = await session.execute(cust_stmt)
            customers = {r[0]: {"name": r[1] or "", "phone": r[2] or ""} for r in cust_res.fetchall()}
        else:
            customers = {}

        # Batch fetch time slots
        slot_ids = [r[3] for r in rows if r[3]]
        if slot_ids:
            ts_stmt = _select(WaveTimeSlot.id, WaveTimeSlot.from_time, WaveTimeSlot.to_time).where(
                WaveTimeSlot.id.in_(slot_ids)
            )
            ts_res = await session.execute(ts_stmt)
            time_slots = {r[0]: f"{r[1].isoformat()}–{r[2].isoformat()}" for r in ts_res.fetchall()}
        else:
            time_slots = {}

        # Count items per order
        from app.modules.orders.models import OrderItem
        item_stmt = _select(OrderItem.order_id, func.count(OrderItem.id)).where(
            OrderItem.order_id.in_(order_ids)
        ).group_by(OrderItem.order_id)
        item_res = await session.execute(item_stmt)
        item_counts = {str(r[0]): r[1] for r in item_res.fetchall()}

        manifest = []
        for row in rows:
            order_id, number, customer_id, time_slot_id, total, currency, order_status = row
            pay = payments.get(order_id, {})
            ful = fulfillments.get(order_id, "unfulfilled")
            cust = customers.get(customer_id, {"name": "", "phone": ""})
            slot = time_slots.get(time_slot_id, "")
            manifest.append({
                "order_id": str(order_id),
                "order_number": number,
                "customer_name": cust["name"],
                "customer_phone": cust["phone"],
                "total": str(total),
                "currency": currency,
                "payment_method": pay.get("method", "unknown"),
                "payment_status": pay.get("status", "unpaid"),
                "fulfillment_status": ful,
                "time_slot": slot,
                "items_count": item_counts.get(str(order_id), 0),
            })

        return manifest
