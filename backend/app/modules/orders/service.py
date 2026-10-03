import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict

from sqlalchemy import select, func, String
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.outbox import emit
from app.modules.orders.models import Order, OrderItem, OrderStatusLog
from app.modules.payments.models import PaymentTransaction, Fulfillment
from app.modules.audit.service import write_audit


VALID_ORDER_TRANSITIONS = {
    "new": {"confirmed", "cancelled"},
    "confirmed": {"completed", "cancelled", "no_show"},
    "cancelled": set(),
    "completed": set(),
    "no_show": set(),
}


class OrderCreateError(Exception):
    pass


class WaveNotCollectingError(Exception):
    pass


class OrderService:
    @staticmethod
    async def _get_or_create_customer(session: AsyncSession, shop_id: uuid.UUID, user_id: uuid.UUID, user_obj: any) -> uuid.UUID:
        """Ensures a customer exists for the given user in the specific shop."""
        from app.modules.auth.models import Customer, CustomerIdentity
        
        # Check if identity exists
        stmt = select(CustomerIdentity).where(
            CustomerIdentity.provider == "telegram",
            CustomerIdentity.external_id == str(user_id) # Note: users.id is UUID, but identity expects string
        )
        # Actually, based on the migration, external_id is String(200). 
        # But wait, if we use the platform user_id as external_id, that's fine.
        # However, typically we'd use telegram_id. 
        # For simplicity here, let's use the platform user_id.
        
        res = await session.execute(stmt)
        ident = res.scalar_one_or_none()
        if ident:
            return ident.customer_id
        
        # Create new customer
        customer = Customer(
            id=uuid.uuid4(),
            shop_id=shop_id,
            display_name=getattr(user_obj, "first_name", "Customer"),
            total_orders=0,
            total_spent=Decimal("0"),
            avg_order_value=Decimal("0"),
        )
        session.add(customer)
        await session.flush()
        
        ident = CustomerIdentity(
            id=uuid.uuid4(),
            customer_id=customer.id,
            provider="telegram",
            external_id=str(user_id),
            username=getattr(user_obj, "username", None),
            metadata={},
        )
        session.add(ident)
        await session.flush()
        
        return customer.id

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        wave_id: Optional[uuid.UUID] = None,
        zone_id: Optional[uuid.UUID] = None,
        pickup_point_id: Optional[uuid.UUID] = None,
        time_slot_id: Optional[uuid.UUID] = None,
        items: List[Dict] = None,
        idempotency_key: Optional[str] = None,
        discount_amount: Decimal = Decimal("0"),
        notes: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
        current_user: any = None,
    ) -> Order:
        if items is None:
            items = []

        # ── Idempotency ────────────────────────────────────────────────────────
        if idempotency_key:
            stmt = select(Order).where(Order.idempotency_key == idempotency_key)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        # ── Resolve Customer ────────────────────────────────────────────────────
        if not customer_id and current_user:
            customer_id = await OrderService._get_or_create_customer(
                session, shop_id, current_user.id, current_user
            )
        
        if not customer_id:
            raise OrderCreateError("Customer is required")

        # ── Validate wave ──────────────────────────────────────────────────────
        wave = None
        if wave_id:
            from app.modules.waves.models import Wave
            stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id)
            res = await session.execute(stmt)
            wave = res.scalar_one_or_none()
            if not wave:
                raise OrderCreateError("Wave not found")
            if wave.status != "collecting":
                raise WaveNotCollectingError(f"Wave is not collecting: {wave.status}")
            if wave.capacity_orders and wave.orders_count >= wave.capacity_orders:
                raise OrderCreateError("Wave is at capacity")

        # ── Generate order number ──────────────────────────────────────────────
        stmt = select(func.max(Order.number)).where(Order.shop_id == shop_id)
        res = await session.execute(stmt)
        last = res.scalar_one_or_none() or 0
        number = last + 1

        # ── Generate QR code ───────────────────────────────────────────────────
        import secrets
        qr_code = f"QR-{secrets.token_hex(6).upper()}"

        order = Order(
            id=uuid.uuid4(),
            shop_id=shop_id,
            customer_id=customer_id,
            number=number,
            wave_id=wave_id,
            zone_id=zone_id or (wave.zone_id if wave else None),
            pickup_point_id=pickup_point_id or (wave.pickup_point_id if wave else None),
            time_slot_id=time_slot_id,
            idempotency_key=idempotency_key,
            qr_code=qr_code,
            discount_amount=discount_amount,
            notes=notes,
        )
        session.add(order)
        await session.flush()

        # ── Create items + reserve inventory ──────────────────────────────────
        from app.modules.catalog.service import CatalogService
        from app.modules.catalog.price_service import PriceService
        from app.modules.inventory.service import InventoryService, InsufficientStockError

        subtotal = Decimal("0")
        for item_data in items:
            product_id = item_data.get("product_id")
            variant_id = item_data.get("variant_id")
            qty = Decimal(str(item_data.get("qty", "1")))

            product = await CatalogService.get_product(session, product_id=product_id, shop_id=shop_id)
            if not product:
                raise OrderCreateError(f"Product {product_id} not found in shop {shop_id}")

            name = product.name
            variant_name = None
            sku = product.sku
            unit_short = None
            cost_price = product.cost_price

            # Fetch unit separately to avoid lazy-load greenlet issues
            if product.unit_id:
                from app.modules.catalog.models import Unit
                u_stmt = select(Unit).where(Unit.id == product.unit_id, Unit.shop_id == shop_id)
                u_res = await session.execute(u_stmt)
                unit_obj = u_res.scalar_one_or_none()
                if unit_obj:
                    unit_short = unit_obj.short_name

            if variant_id:
                from app.modules.catalog.models import ProductVariant
                v_stmt = select(ProductVariant).where(
                    ProductVariant.id == variant_id,
                    ProductVariant.shop_id == shop_id,
                )
                v_res = await session.execute(v_stmt)
                v = v_res.scalar_one_or_none()
                if v:
                    variant_name = v.name
                    sku = v.sku or sku
                    cost_price = v.cost_price

            price_result = await PriceService.get_active_price(session, product_id=product_id, variant_id=variant_id)
            unit_price = price_result.amount if price_result else Decimal("0")

            item_discount = Decimal(str(item_data.get("discount_amount", "0")))
            item_subtotal = qty * unit_price - item_discount
            if item_subtotal < 0:
                item_subtotal = Decimal("0")
            subtotal += item_subtotal

            order_item = OrderItem(
                id=uuid.uuid4(),
                order_id=order.id,
                product_id=product_id,
                variant_id=variant_id,
                product_name=name,
                variant_name=variant_name,
                sku=sku,
                unit_short=unit_short,
                qty=qty,
                unit_price=unit_price,
                cost_price=cost_price,
                discount_amount=item_discount,
                subtotal=item_subtotal,
            )
            session.add(order_item)

            if product.stock_tracking:
                try:
                    from app.modules.inventory.models import InventoryItem
                    inv_stmt = select(InventoryItem).where(
                        InventoryItem.shop_id == shop_id,
                        InventoryItem.product_id == product_id,
                        InventoryItem.variant_id == variant_id,
                    )
                    inv_res = await session.execute(inv_stmt)
                    inv_item = inv_res.scalar_one_or_none()
                    if inv_item:
                        try:
                            await InventoryService.reserve(
                                session,
                                inventory_id=inv_item.id,
                                qty=qty,
                                order_id=order.id,
                                ttl_minutes=30,
                            )
                        except InsufficientStockError:
                            raise OrderCreateError(
                                f"Insufficient stock for product {product_id}: requested {qty}"
                            )
                except Exception:
                    pass

        order.subtotal = subtotal
        order.total = subtotal - discount_amount
        if order.total < 0:
            order.total = Decimal("0")
        await session.flush()

        # ── Create fulfillment record ──────────────────────────────────────────
        fulfillment = Fulfillment(
            id=uuid.uuid4(),
            order_id=order.id,
            wave_id=wave_id,
            delivery_date=wave.delivery_date if wave else None,
        )
        session.add(fulfillment)

        # ── INV-010: emit outbox event ──────────────────────────────────────────
        await emit(
            session,
            shop_id=shop_id,
            event_type="order.created",
            aggregate_type="order",
            aggregate_id=order.id,
            payload={
                "order_id": str(order.id),
                "number": order.number,
                "total": str(order.total),
                "qr_code": qr_code,
                "wave_id": str(wave_id) if wave_id else None,
            },
        )

        # ── INV-011: audit log ─────────────────────────────────────────────────
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ORDER_CREATED", entity_type="order", entity_id=order.id,
            after={"number": order.number, "total": str(order.total),
                   "status": "new", "qr_code": qr_code},
        )

        # ── Log status ─────────────────────────────────────────────────────────
        await OrderService._log_status_change(
            session, order_id=order.id, field="order_status",
            old_value=None, new_value="new", changed_by=created_by,
        )

        if wave:
            wave.orders_count += 1
            wave.items_count += len(items)
            wave.revenue_total = (wave.revenue_total or Decimal("0")) + order.total
            from datetime import datetime as _dt
            wave.updated_at = _dt.now(timezone.utc)

        return order

    @staticmethod
    async def _log_status_change(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        field: str,
        old_value: Optional[str],
        new_value: str,
        changed_by: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ):
        log = OrderStatusLog(
            id=uuid.uuid4(),
            order_id=order_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            note=note,
        )
        session.add(log)

    @staticmethod
    async def transition_order_status(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        shop_id: uuid.UUID,
        new_status: str,
        created_by: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ) -> Order:
        stmt = select(Order).where(Order.id == order_id, Order.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found in shop {shop_id}")

        current = order.order_status
        if new_status not in VALID_ORDER_TRANSITIONS.get(current, set()):
            raise ValueError(f"Invalid transition: {current} → {new_status}")

        await OrderService._log_status_change(
            session, order_id=order_id, field="order_status",
            old_value=current, new_value=new_status,
            changed_by=created_by, note=note,
        )
        order.order_status = new_status
        from datetime import datetime as _dt
        order.updated_at = _dt.now(timezone.utc)

        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ORDER_STATUS_CHANGED", entity_type="order", entity_id=order_id,
            before={"status": current},
            after={"status": new_status},
        )

        await emit(
            session, shop_id=shop_id,
            event_type=f"order.{new_status}",
            aggregate_type="order", aggregate_id=order_id,
            payload={"order_id": str(order_id), "status": new_status},
        )

        return order

    @staticmethod
    async def cancel_order(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Order:
        order = await OrderService.transition_order_status(
            session, order_id=order_id, shop_id=shop_id,
            new_status="cancelled", created_by=created_by
        )

        from app.modules.inventory.service import InventoryService, ReservationNotFoundError
        from app.modules.inventory.models import InventoryReservation
        stmt = select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == "active",
        )
        res = await session.execute(stmt)
        reservations = res.scalars().all()
        for reservation in reservations:
            try:
                await InventoryService.release(session, reservation_id=reservation.id)
            except ReservationNotFoundError:
                pass

        await emit(
            session, shop_id=shop_id,
            event_type="order.cancelled",
            aggregate_type="order", aggregate_id=order_id,
            payload={"order_id": str(order_id), "status": "cancelled"},
        )

        return order

    @staticmethod
    async def list_orders(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        status: Optional[str] = None,
        wave_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[Order]:
        stmt = select(Order).options(selectinload(Order.items), selectinload(Order.status_log))\
            .where(Order.shop_id == shop_id)
        if status:
            stmt = stmt.where(Order.order_status == status)
        if wave_id:
            stmt = stmt.where(Order.wave_id == wave_id)
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_order(
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[Order]:
        stmt = select(Order).options(selectinload(Order.items), selectinload(Order.status_log))\
            .where(Order.id == order_id, Order.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_order_by_qr(session: AsyncSession, *, qr_code: str) -> Optional[Order]:
        stmt = select(Order).where(Order.qr_code == qr_code)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_customer_orders(
        session: AsyncSession,
        *,
        customer_id: uuid.UUID,
        shop_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Order]:
        stmt = select(Order).options(selectinload(Order.items), selectinload(Order.status_log))\
            .where(
                Order.customer_id == customer_id,
                Order.shop_id == shop_id,
            ).order_by(Order.created_at.desc()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_customer_id_for_user(
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        shop_id: uuid.UUID,
    ) -> Optional[uuid.UUID]:
        """Look up customer_id for a platform user within a shop."""
        from app.modules.auth.models import CustomerIdentity, Customer
        ident_stmt = select(CustomerIdentity).where(
            CustomerIdentity.provider == "telegram",
            CustomerIdentity.external_id == str(user_id),
        )
        res = await session.execute(ident_stmt)
        ident = res.scalar_one_or_none()
        if ident:
            return ident.customer_id
        # Try to find customer directly linked to shop via identity
        cust_stmt = select(Customer).where(
            Customer.shop_id == shop_id
        )
        res = await session.execute(cust_stmt)
        # Return first customer if no identity found (for backward compat)
        # Actually, let's just return None and let the caller handle it
        return None
