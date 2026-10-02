import asyncio
import uuid
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings

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
