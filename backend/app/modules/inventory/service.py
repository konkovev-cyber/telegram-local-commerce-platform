from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.audit.service import write_audit
from app.modules.inventory.models import InventoryItem, InventoryMovement, InventoryReservation


class InsufficientStockError(Exception):
    pass


class ReservationNotFoundError(Exception):
    pass


class InventoryService:
    @staticmethod
    async def initialize(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID] = None,
        initial_qty: Decimal = Decimal("0"),
        created_by: Optional[uuid.UUID] = None,
    ) -> InventoryItem:
        item = InventoryItem(
            id=uuid.uuid4(),
            shop_id=shop_id,
            product_id=product_id,
            variant_id=variant_id,
            available_qty=initial_qty,
            reserved_qty=Decimal("0"),
            sold_qty=Decimal("0"),
        )
        session.add(item)
        if initial_qty > 0:
            session.add(InventoryMovement(
                shop_id=shop_id,
                inventory_id=item.id,
                type="purchase",
                qty=initial_qty,
                before_available=Decimal("0"),
                after_available=initial_qty,
                created_by=created_by,
            ))
        await session.flush()
        return item

    @staticmethod
    async def reserve(
        session: AsyncSession,
        *,
        inventory_id: uuid.UUID,
        qty: Decimal,
        order_id: Optional[uuid.UUID] = None,
        ttl_minutes: int = 15,
    ) -> InventoryReservation:
        if qty <= 0:
            raise ValueError("qty must be positive")

        stmt = select(InventoryItem).where(InventoryItem.id == inventory_id).with_for_update()
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ReservationNotFoundError(f"Inventory item {inventory_id} not found")

        if item.available_qty < qty:
            raise InsufficientStockError(
                f"Requested {qty}, available {item.available_qty}"
            )

        before = item.available_qty
        item.available_qty -= qty
        item.reserved_qty += qty

        reservation = InventoryReservation(
            id=uuid.uuid4(),
            inventory_id=inventory_id,
            order_id=order_id,
            qty=qty,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
            status="active",
        )
        session.add(reservation)

        session.add(InventoryMovement(
            shop_id=item.shop_id,
            inventory_id=inventory_id,
            type="reservation",
            qty=-qty,
            before_available=before,
            after_available=item.available_qty,
            reference_type="order",
            reference_id=order_id,
        ))
        return reservation

    @staticmethod
    async def sell(
        session: AsyncSession,
        *,
        reservation_id: uuid.UUID,
    ) -> None:
        stmt = select(InventoryReservation).where(
            InventoryReservation.id == reservation_id,
            InventoryReservation.status == "active",
        )
        res = await session.execute(stmt)
        reservation = res.scalar_one_or_none()
        if not reservation:
            raise ReservationNotFoundError(f"Reservation {reservation_id} not found or not active")

        item_stmt = select(InventoryItem).where(InventoryItem.id == reservation.inventory_id).with_for_update()
        item_res = await session.execute(item_stmt)
        item = item_res.scalar_one_or_none()
        if not item:
            raise ReservationNotFoundError(f"Inventory item {reservation.inventory_id} not found")

        before = item.available_qty
        item.available_qty += reservation.qty
        item.reserved_qty -= reservation.qty
        item.sold_qty += reservation.qty
        reservation.status = "sold"

        session.add(InventoryMovement(
            shop_id=item.shop_id,
            inventory_id=reservation.inventory_id,
            type="sale",
            qty=-reservation.qty,
            before_available=before,
            after_available=item.available_qty,
            reference_type="order",
            reference_id=reservation.order_id,
        ))

    @staticmethod
    async def release(
        session: AsyncSession,
        *,
        reservation_id: uuid.UUID,
    ) -> None:
        stmt = select(InventoryReservation).where(
            InventoryReservation.id == reservation_id,
            InventoryReservation.status == "active",
        )
        res = await session.execute(stmt)
        reservation = res.scalar_one_or_none()
        if not reservation:
            raise ReservationNotFoundError(f"Reservation {reservation_id} not found or not active")

        item_stmt = select(InventoryItem).where(InventoryItem.id == reservation.inventory_id).with_for_update()
        item_res = await session.execute(item_stmt)
        item = item_res.scalar_one_or_none()
        if not item:
            raise ReservationNotFoundError(f"Inventory item {reservation.inventory_id} not found")

        before = item.available_qty
        item.available_qty += reservation.qty
        item.reserved_qty -= reservation.qty
        reservation.status = "released"

        session.add(InventoryMovement(
            shop_id=item.shop_id,
            inventory_id=reservation.inventory_id,
            type="reservation_release",
            qty=reservation.qty,
            before_available=before,
            after_available=item.available_qty,
            reference_type="reservation",
            reference_id=reservation_id,
        ))

    @staticmethod
    async def correct(
        session: AsyncSession,
        *,
        inventory_id: uuid.UUID,
        new_qty: Decimal,
        note: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> InventoryItem:
        stmt = select(InventoryItem).where(InventoryItem.id == inventory_id).with_for_update()
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise ReservationNotFoundError(f"Inventory item {inventory_id} not found")

        before = item.available_qty
        diff = new_qty - before
        item.available_qty = new_qty

        session.add(InventoryMovement(
            shop_id=item.shop_id,
            inventory_id=inventory_id,
            type="correction",
            qty=diff,
            before_available=before,
            after_available=new_qty,
            note=note,
            created_by=created_by,
        ))
        return item

    @staticmethod
    async def release_expired(
        session: AsyncSession,
    ) -> int:
        now = datetime.now(timezone.utc)
        stmt = select(InventoryReservation).where(
            InventoryReservation.status == "active",
            InventoryReservation.expires_at < now,
        )
        res = await session.execute(stmt)
        expired = res.scalars().all()
        for r in expired:
            try:
                await InventoryService.release(session, reservation_id=r.id)
            except Exception:
                pass
        return len(expired)
