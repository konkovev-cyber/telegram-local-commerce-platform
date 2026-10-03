import uuid
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.waves.models import Wave, WaveTimeSlot
from app.modules.audit.service import write_audit


VALID_TRANSITIONS = {
    "collecting": {"closed", "cancelled"},
    "closed": {"assembling"},
    "assembling": {"delivering", "closed"},
    "delivering": {"done"},
    "cancelled": set(),
    "done": set(),
}


class WaveService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        zone_id: uuid.UUID,
        pickup_point_id: Optional[uuid.UUID] = None,
        name: Optional[str] = None,
        opens_at: Optional[datetime] = None,
        closes_at: datetime = None,
        delivery_date: date = None,
        delivery_from: time = None,
        delivery_to: time = None,
        capacity_orders: Optional[int] = None,
        min_orders: Optional[int] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Wave:
        if delivery_date is None:
            delivery_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        if delivery_from is None:
            delivery_from = time(10, 0)
        if delivery_to is None:
            delivery_to = time(20, 0)
        if closes_at is None:
            closes_at = datetime.now(timezone.utc) + timedelta(hours=12)

        # Get next wave number
        stmt = select(func.max(Wave.number)).where(Wave.shop_id == shop_id)
        res = await session.execute(stmt)
        last = res.scalar_one_or_none() or 0
        number = last + 1

        wave = Wave(
            shop_id=shop_id,
            zone_id=zone_id,
            pickup_point_id=pickup_point_id,
            number=number,
            name=name,
            opens_at=opens_at,
            closes_at=closes_at,
            delivery_date=delivery_date,
            delivery_from=delivery_from,
            delivery_to=delivery_to,
            capacity_orders=capacity_orders,
            min_orders=min_orders,
        )
        session.add(wave)
        await session.flush()
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_CREATED", entity_type="wave", entity_id=wave.id,
            after={"number": number, "status": wave.status, "delivery_date": str(delivery_date)},
        )
        return wave

    @staticmethod
    async def list(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        status_filter: Optional[str] = None,
        zone_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List[Wave]:
        stmt = select(Wave).where(Wave.shop_id == shop_id)
        if status_filter:
            stmt = stmt.where(Wave.status == status_filter)
        if zone_id:
            stmt = stmt.where(Wave.zone_id == zone_id)
        stmt = stmt.order_by(Wave.delivery_date.desc(), Wave.number.desc())
        stmt = stmt.limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, *, wave_id: uuid.UUID, shop_id: uuid.UUID) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def close(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        if wave.status != "collecting":
            raise ValueError(f"Wave is not in collecting state, current: {wave.status}")
        old_status = wave.status
        wave.status = "closed"
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_CLOSED", entity_type="wave", entity_id=wave.id,
            before={"status": old_status},
            after={"status": "closed", "orders_count": wave.orders_count},
        )
        return wave

    @staticmethod
    async def cancel(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        reason: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        if wave.status not in ("collecting", "closed"):
            raise ValueError(f"Cannot cancel wave in status: {wave.status}")
        old_status = wave.status
        wave.status = "cancelled"
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_CANCELLED", entity_type="wave", entity_id=wave.id,
            before={"status": old_status},
            after={"status": "cancelled", "reason": reason},
        )
        return wave

    @staticmethod
    async def advance_to_assembling(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        if wave.status != "closed":
            raise ValueError(f"Wave must be closed to start assembling, current: {wave.status}")
        old_status = wave.status
        wave.status = "assembling"
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_ASSEMBLING", entity_type="wave", entity_id=wave.id,
            before={"status": old_status},
            after={"status": "assembling"},
        )
        return wave

    @staticmethod
    async def advance_to_delivering(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        if wave.status != "assembling":
            raise ValueError(f"Wave must be assembling, current: {wave.status}")
        old_status = wave.status
        wave.status = "delivering"
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_DELIVERING", entity_type="wave", entity_id=wave.id,
            before={"status": old_status},
            after={"status": "delivering"},
        )
        return wave

    @staticmethod
    async def advance_to_done(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Wave]:
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id).with_for_update()
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        if wave.status != "delivering":
            raise ValueError(f"Wave must be delivering, current: {wave.status}")
        old_status = wave.status
        wave.status = "done"
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="WAVE_DONE", entity_type="wave", entity_id=wave.id,
            before={"status": old_status},
            after={"status": "done", "orders_count": wave.orders_count},
        )
        return wave

    @staticmethod
    async def update_stats(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        shop_id: uuid.UUID,
        orders_delta: int = 0,
        items_delta: int = 0,
        revenue_delta: Decimal = Decimal("0"),
    ) -> Optional[Wave]:
        """Incremental stat update — called from order/payment hooks."""
        stmt = select(Wave).where(Wave.id == wave_id, Wave.shop_id == shop_id)
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return None
        wave.orders_count += orders_delta
        wave.items_count += items_delta
        wave.revenue_total = (wave.revenue_total or Decimal("0")) + revenue_delta
        from datetime import datetime as _dt
        wave.updated_at = _dt.now(timezone.utc)
        return wave

    @staticmethod
    async def list_time_slots(session: AsyncSession, *, wave_id: uuid.UUID) -> List[WaveTimeSlot]:
        stmt = select(WaveTimeSlot).where(WaveTimeSlot.wave_id == wave_id).order_by(WaveTimeSlot.from_time)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_time_slot(
        session: AsyncSession,
        *,
        wave_id: uuid.UUID,
        from_time: time,
        to_time: time,
        max_orders: Optional[int] = None,
    ) -> WaveTimeSlot:
        slot = WaveTimeSlot(wave_id=wave_id, from_time=from_time, to_time=to_time, max_orders=max_orders)
        session.add(slot)
        await session.flush()
        return slot

    @staticmethod
    async def delete_time_slot(session: AsyncSession, *, slot_id: uuid.UUID, wave_id: uuid.UUID) -> bool:
        stmt = select(WaveTimeSlot).where(WaveTimeSlot.id == slot_id, WaveTimeSlot.wave_id == wave_id)
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()
        if not slot:
            return False
        await session.delete(slot)
        return True
