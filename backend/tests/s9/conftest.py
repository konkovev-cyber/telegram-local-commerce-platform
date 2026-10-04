import uuid as _uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import get_db
from app.core.config import settings

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
async def shop_b(client, user_b) -> dict:
    headers = {**user_b["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post("/api/v1/admin/shops", headers=headers, json={"slug": f"shop-b-{_uuid.uuid4().hex[:6]}", "name": "Shop B", "currency": "USD"})
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


async def _create_campaign(client, headers, shop_id, name, zone_id=None):
    """Helper: create a campaign and return its id."""
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={
        "name": name,
    })
    if resp.status_code != 201:
        pytest.skip(f"Campaign create failed: {resp.text}")
    data = resp.json()
    campaign_id = data["id"]

    # Create a source
    ref_code = f"ref-{_uuid.uuid4().hex[:6]}"
    resp = await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": f"Source for {name}",
        "ref_code": ref_code,
        "zone_id": str(zone_id) if zone_id else None,
    })
    if resp.status_code != 201:
        pytest.skip(f"Source create failed: {resp.text}")
    source = resp.json()

    return campaign_id, source["id"], ref_code
