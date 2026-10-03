"""S2-A catalog test fixtures — async-safe engine per test."""
import asyncio
import hmac
import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.db import get_db
from app.core.config import settings
from app.modules.auth.jwt import create_access_token

TEST_DB_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)


def make_telegram_init_data(user_data: dict, bot_token: str = settings.platform_bot_token) -> str:
    params = {
        "user": json.dumps(user_data, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={v}" for k, v in params.items())


@pytest_asyncio.fixture(scope="session")
async def _setup_db():
    """One-time session setup: ensure schema exists."""
    from app.core.db import Base
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(_setup_db):
    """Per-test session using fresh engine to avoid loop conflicts."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


def make_token(user_id: uuid.UUID) -> str:
    return create_access_token(data={"sub": str(user_id)})


@pytest_asyncio.fixture()
async def user_a(client) -> dict:
    init_data = make_telegram_init_data({"id": 100001, "first_name": "Alice"})
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    data = resp.json()
    return {
        "user_id": uuid.UUID(data["user_id"]),
        "token": data["access_token"],
        "auth_headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest_asyncio.fixture()
async def user_b(client) -> dict:
    init_data = make_telegram_init_data({"id": 100002, "first_name": "Bob"})
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 200
    data = resp.json()
    return {
        "user_id": uuid.UUID(data["user_id"]),
        "token": data["access_token"],
        "auth_headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest_asyncio.fixture()
async def shop_a(client, user_a) -> dict:
    headers = {**user_a["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post(
        "/api/v1/admin/shops", headers=headers,
        json={"slug": f"shop-a-{uuid.uuid4().hex[:6]}", "name": "Shop A", "currency": "RUB"},
    )
    assert resp.status_code == 201, f"Shop create failed: {resp.text}"
    shop = resp.json()
    return {"shop_id": uuid.UUID(shop["id"]), "shop": shop}


@pytest_asyncio.fixture()
async def shop_b(client, user_b) -> dict:
    headers = {**user_b["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post(
        "/api/v1/admin/shops", headers=headers,
        json={"slug": f"shop-b-{uuid.uuid4().hex[:6]}", "name": "Shop B", "currency": "USD"},
    )
    assert resp.status_code == 201
    shop = resp.json()
    return {"shop_id": uuid.UUID(shop["id"]), "shop": shop}
