import uuid as _uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.core.db import get_db
from app.core.config import settings
from app.core.outbox import OutboxEvent

TEST_DATABASE_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)


def make_token(user_id: _uuid.UUID) -> str:
    from app.modules.auth.jwt import create_access_token
    return create_access_token(data={"sub": str(user_id)})


def make_telegram_init_data(user_data, bot_token=settings.platform_bot_token):
    import hmac, hashlib, json, time
    auth_date = int(time.time())
    params = {"user": json.dumps(user_data, separators=(",", ":")), "auth_date": str(auth_date)}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={v}" for k, v in params.items())


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session) -> AsyncClient:
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def user_a(client) -> dict:
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": make_telegram_init_data({"id": 100001, "first_name": "Alice"})})
    assert resp.status_code == 200
    data = resp.json()
    return {"user_id": _uuid.UUID(data["user_id"]), "token": data["access_token"], "auth_headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest_asyncio.fixture()
async def user_b(client) -> dict:
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": make_telegram_init_data({"id": 100002, "first_name": "Bob"})})
    assert resp.status_code == 200
    data = resp.json()
    return {"user_id": _uuid.UUID(data["user_id"]), "token": data["access_token"], "auth_headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest_asyncio.fixture()
async def shop_a(client, user_a) -> dict:
    headers = {**user_a["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post("/api/v1/admin/shops", headers=headers, json={"slug": f"shop-a-{_uuid.uuid4().hex[:6]}", "name": "Shop A", "currency": "RUB"})
    assert resp.status_code == 201
    shop = resp.json()
    return {"shop_id": _uuid.UUID(shop["id"]), "shop": shop}


@pytest_asyncio.fixture()
async def zone_a(client, user_a, shop_a) -> dict:
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    slug = f"zone-{_uuid.uuid4().hex[:6]}"
    resp = await client.post("/api/v1/admin/geo/zones", headers=headers, json={"name": "Center", "slug": slug})
    assert resp.status_code == 201
    zone = resp.json()
    return {"zone_id": _uuid.UUID(zone["id"]), "zone": zone}


@pytest_asyncio.fixture()
async def wave_a(client, user_a, shop_a, zone_a) -> dict:
    from datetime import date, datetime, timezone, timedelta
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    assert resp.status_code == 201
    wave = resp.json()
    return {"wave_id": _uuid.UUID(wave["id"]), "wave": wave}


@pytest_asyncio.fixture()
async def product_with_inventory(db_session, shop_a) -> tuple:
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService
    from sqlalchemy import select
    from app.modules.catalog.models import Unit
    from decimal import Decimal as D

    stmt = select(Unit).where(Unit.shop_id == shop_a["shop_id"]).limit(1)
    res = await db_session.execute(stmt)
    unit = res.scalar_one_or_none()
    if not unit:
        unit = await CatalogService.create_unit(db_session, shop_id=shop_a["shop_id"], name=" шт", short_name=" шт")
        await db_session.flush()

    product = await CatalogService.create_product(
        db_session, shop_id=shop_a["shop_id"],
        name="S8 Test Product", slug=f"s8prod-{_uuid.uuid4().hex[:8]}",
        sku=f"S8PROD-{_uuid.uuid4().hex[:8]}", unit_id=unit.id,
    )
    await db_session.flush()

    inventory = await InventoryService.initialize(
        db_session, shop_id=shop_a["shop_id"], product_id=product.id,
        initial_qty=D("100"),
    )
    await db_session.commit()
    return product, inventory


def _make_outbox_event(session: AsyncSession, *, shop_id, event_type, aggregate_type, aggregate_id, payload):
    """Helper to insert an outbox event directly into DB."""
    from app.core.outbox import OutboxEvent
    import uuid as _uuid
    event = OutboxEvent(
        id=_uuid.uuid4(),
        shop_id=shop_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status="pending",
        attempts=0,
    )
    session.add(event)
    return event
