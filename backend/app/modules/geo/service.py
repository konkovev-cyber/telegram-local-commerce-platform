import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.geo.models import Zone, PickupPoint
from app.modules.audit.service import write_audit


class ZoneService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        name: str,
        slug: str,
        created_by: Optional[uuid.UUID] = None,
    ) -> Zone:
        zone = Zone(shop_id=shop_id, name=name, slug=slug)
        session.add(zone)
        await session.flush()
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ZONE_CREATED", entity_type="zone", entity_id=zone.id,
            after={"name": name, "slug": slug},
        )
        return zone

    @staticmethod
    async def list(session: AsyncSession, *, shop_id: uuid.UUID, active_only: bool = True) -> List[Zone]:
        stmt = select(Zone).where(Zone.shop_id == shop_id)
        if active_only:
            stmt = stmt.where(Zone.is_active == True)
        stmt = stmt.order_by(Zone.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, *, zone_id: uuid.UUID, shop_id: uuid.UUID) -> Optional[Zone]:
        stmt = select(Zone).where(Zone.id == zone_id, Zone.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def update(
        session: AsyncSession,
        *,
        zone_id: uuid.UUID,
        shop_id: uuid.UUID,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[Zone]:
        stmt = select(Zone).where(Zone.id == zone_id, Zone.shop_id == shop_id)
        res = await session.execute(stmt)
        zone = res.scalar_one_or_none()
        if not zone:
            return None
        before = {"name": zone.name, "is_active": zone.is_active}
        if name is not None:
            zone.name = name
        if is_active is not None:
            zone.is_active = is_active
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="ZONE_UPDATED", entity_type="zone", entity_id=zone.id,
            before=before,
            after={"name": zone.name, "is_active": zone.is_active},
        )
        return zone

    @staticmethod
    async def delete(session: AsyncSession, *, zone_id: uuid.UUID, shop_id: uuid.UUID) -> bool:
        stmt = select(Zone).where(Zone.id == zone_id, Zone.shop_id == shop_id)
        res = await session.execute(stmt)
        zone = res.scalar_one_or_none()
        if not zone:
            return False
        await session.delete(zone)
        return True


class PickupPointService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        zone_id: uuid.UUID,
        name: str,
        address: Optional[str] = None,
        lat: Optional[Decimal] = None,
        lon: Optional[Decimal] = None,
        maps_url: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> PickupPoint:
        point = PickupPoint(
            shop_id=shop_id, zone_id=zone_id, name=name,
            address=address, lat=lat, lon=lon, maps_url=maps_url,
        )
        session.add(point)
        await session.flush()
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="PICKUP_POINT_CREATED", entity_type="pickup_point", entity_id=point.id,
            after={"name": name, "zone_id": str(zone_id)},
        )
        return point

    @staticmethod
    async def list(session: AsyncSession, *, shop_id: uuid.UUID, zone_id: Optional[uuid.UUID] = None) -> List[PickupPoint]:
        stmt = select(PickupPoint).where(PickupPoint.shop_id == shop_id)
        if zone_id:
            stmt = stmt.where(PickupPoint.zone_id == zone_id)
        stmt = stmt.order_by(PickupPoint.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, *, point_id: uuid.UUID, shop_id: uuid.UUID) -> Optional[PickupPoint]:
        stmt = select(PickupPoint).where(PickupPoint.id == point_id, PickupPoint.shop_id == shop_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def update(
        session: AsyncSession,
        *,
        point_id: uuid.UUID,
        shop_id: uuid.UUID,
        name: Optional[str] = None,
        address: Optional[str] = None,
        is_active: Optional[bool] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> Optional[PickupPoint]:
        stmt = select(PickupPoint).where(PickupPoint.id == point_id, PickupPoint.shop_id == shop_id)
        res = await session.execute(stmt)
        point = res.scalar_one_or_none()
        if not point:
            return None
        before = {"name": point.name, "is_active": point.is_active}
        if name is not None:
            point.name = name
        if address is not None:
            point.address = address
        if is_active is not None:
            point.is_active = is_active
        await write_audit(
            session, shop_id=shop_id, actor_id=created_by,
            action="PICKUP_POINT_UPDATED", entity_type="pickup_point", entity_id=point.id,
            before=before,
            after={"name": point.name, "is_active": point.is_active},
        )
        return point

    @staticmethod
    async def delete(session: AsyncSession, *, point_id: uuid.UUID, shop_id: uuid.UUID) -> bool:
        stmt = select(PickupPoint).where(PickupPoint.id == point_id, PickupPoint.shop_id == shop_id)
        res = await session.execute(stmt)
        point = res.scalar_one_or_none()
        if not point:
            return False
        await session.delete(point)
        return True
