"""
S1 test fixtures.
Uses a separate test database, real PostgreSQL (no mocks).
"""
import hmac
import hashlib
import json
import time
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings
from app.modules.auth.jwt import create_access_token
from app.modules.auth.service import UserService
from app.modules.shops.service import ShopService

TEST_DATABASE_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session(setup_db) -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


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


def make_telegram_init_data(
    user_data: dict,
    bot_token: str = settings.platform_bot_token,
    auth_date: int | None = None,
) -> str:
    """Build a valid Telegram initData string with correct HMAC."""
    if auth_date is None:
        auth_date = int(time.time())
    params = {
        "user": json.dumps(user_data, separators=(",", ":")),
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = computed_hash
    return "&".join(f"{k}={v}" for k, v in params.items())


@pytest_asyncio.fixture()
async def user_a(db_session) -> dict:
    """Create user A and return dict with user, token, auth_headers."""
    user = await UserService.create(
        db_session,
        telegram_id=111111,
        first_name="Alice",
        platform_role="user",
    )
    await db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "user": user,
        "token": token,
        "auth_headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture()
async def user_b(db_session) -> dict:
    """Create user B and return dict with user, token, auth_headers."""
    user = await UserService.create(
        db_session,
        telegram_id=222222,
        first_name="Bob",
        platform_role="user",
    )
    await db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "user": user,
        "token": token,
        "auth_headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture()
async def shop_a(db_session, user_a) -> dict:
    """Create shop A owned by user A."""
    shop = await ShopService.create(
        db_session,
        slug=f"shop-a-{uuid.uuid4().hex[:6]}",
        name="Shop A",
        owner_id=user_a["user"].id,
        currency="RUB",
    )
    await db_session.commit()
    return {"shop": shop}


@pytest_asyncio.fixture()
async def shop_b(db_session, user_b) -> dict:
    """Create shop B owned by user B."""
    shop = await ShopService.create(
        db_session,
        slug=f"shop-b-{uuid.uuid4().hex[:6]}",
        name="Shop B",
        owner_id=user_b["user"].id,
        currency="USD",
    )
    await db_session.commit()
    return {"shop": shop}
