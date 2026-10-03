import asyncio
import uuid
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text as sa_text

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings
from app.modules.orders.models import Order, OrderItem  # noqa: register models in Base.metadata

TEST_DATABASE_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)


@pytest_asyncio.fixture(scope="session")
async def _setup_db():
    """One-time session setup: ensure schema exists."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.execute(sa_text("DROP SCHEMA public CASCADE")))
        await conn.run_sync(lambda c: c.execute(sa_text("CREATE SCHEMA public")))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(_setup_db) -> AsyncSession:
    """Per-test session using fresh engine to avoid loop conflicts."""
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
async def shop_and_owner(db_session):
    from app.modules.shops.service import ShopService
    from app.modules.auth.service import UserService

    owner = await UserService.create(
        db_session,
        email=f"owner_{uuid.uuid4().hex[:8]}@test.com",
        password="testpass123",
        platform_role="user",
    )
    shop = await ShopService.create(
        db_session,
        slug=f"test-shop-{uuid.uuid4().hex[:8]}",
        name="Test Shop",
        owner_id=owner.id,
        currency="RUB",
    )
    await db_session.commit()
    return shop, owner
