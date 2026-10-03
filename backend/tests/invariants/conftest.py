import uuid
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text as sa_text
import os

from app.main import app
from app.core.db import get_db
from app.core.config import settings
from app.modules.orders.models import Order, OrderItem  # noqa
from app.modules.inventory.models import InventoryItem, InventoryMovement, InventoryReservation  # noqa
from app.modules.payments.models import Payment, PaymentTransaction, WebhookEvent, Fulfillment  # noqa

TEST_DATABASE_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)


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


def make_telegram_init_data(user_data, bot_token=settings.platform_bot_token):
    import hmac, hashlib, json, time
    auth_date = int(time.time())
    params = {"user": json.dumps(user_data, separators=(",", ":")), "auth_date": str(auth_date)}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={v}" for k, v in params.items())


@pytest_asyncio.fixture()
async def user_a(db_session) -> dict:
    telegram_id = 111111 + int(uuid.uuid4().hex[:4], 16) % 100000
    from app.modules.auth.service import UserService
    from app.modules.auth.jwt import create_access_token
    user = await UserService.create(db_session, telegram_id=telegram_id, first_name="Alice", platform_role="user")
    await db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {"user": user, "token": token, "auth_headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture()
async def user_b(db_session) -> dict:
    telegram_id = 222222 + int(uuid.uuid4().hex[:4], 16) % 100000
    from app.modules.auth.service import UserService
    from app.modules.auth.jwt import create_access_token
    user = await UserService.create(db_session, telegram_id=telegram_id, first_name="Bob", platform_role="user")
    await db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {"user": user, "token": token, "auth_headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture()
async def shop_a(db_session, user_a) -> dict:
    from app.modules.shops.service import ShopService
    shop = await ShopService.create(db_session, slug=f"shop-a-{uuid.uuid4().hex[:6]}", name="Shop A", owner_id=user_a["user"].id, currency="RUB")
    await db_session.commit()
    return {"shop": shop}


@pytest_asyncio.fixture()
async def shop_b(db_session, user_b) -> dict:
    from app.modules.shops.service import ShopService
    shop = await ShopService.create(db_session, slug=f"shop-b-{uuid.uuid4().hex[:6]}", name="Shop B", owner_id=user_b["user"].id, currency="USD")
    await db_session.commit()
    return {"shop": shop}


@pytest_asyncio.fixture()
async def shop_and_owner(db_session):
    from app.modules.shops.service import ShopService
    from app.modules.auth.service import UserService
    owner = await UserService.create(db_session, email=f"owner_{uuid.uuid4().hex[:8]}@test.com", password="testpass123", platform_role="user")
    shop = await ShopService.create(db_session, slug=f"test-shop-{uuid.uuid4().hex[:8]}", name="Test Shop", owner_id=owner.id, currency="RUB")
    await db_session.commit()
    return shop, owner


@pytest_asyncio.fixture()
async def product_with_inventory(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService
    shop, owner = shop_and_owner
    product = await CatalogService.create_product(db_session, shop_id=shop.id, name="Фермерская свинина INV", slug=f"inv-product-{uuid.uuid4().hex[:8]}", sku=f"INV-PROD-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    inventory = await InventoryService.initialize(db_session, shop_id=shop.id, product_id=product.id, initial_qty=Decimal("30.000"), created_by=owner.id)
    await db_session.commit()
    return product, inventory, shop, owner
