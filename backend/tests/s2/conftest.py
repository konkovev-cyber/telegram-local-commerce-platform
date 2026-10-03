import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
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


def make_token(user_id: uuid.UUID) -> str:
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
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    data = resp.json()
    return {"user_id": uuid.UUID(data["user_id"]), "token": data["access_token"], "auth_headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest_asyncio.fixture()
async def user_b(client) -> dict:
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": make_telegram_init_data({"id": 100002, "first_name": "Bob"})})
    assert resp.status_code == 200
    data = resp.json()
    return {"user_id": uuid.UUID(data["user_id"]), "token": data["access_token"], "auth_headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest_asyncio.fixture()
async def shop_a(client, user_a) -> dict:
    headers = {**user_a["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post("/api/v1/admin/shops", headers=headers, json={"slug": f"shop-a-{uuid.uuid4().hex[:6]}", "name": "Shop A", "currency": "RUB"})
    assert resp.status_code == 201, f"Shop create failed: {resp.text}"
    shop = resp.json()
    return {"shop_id": uuid.UUID(shop["id"]), "shop": shop}


@pytest_asyncio.fixture()
async def shop_b(client, user_b) -> dict:
    headers = {**user_b["auth_headers"], "X-Shop-Id": ""}
    resp = await client.post("/api/v1/admin/shops", headers=headers, json={"slug": f"shop-b-{uuid.uuid4().hex[:6]}", "name": "Shop B", "currency": "USD"})
    assert resp.status_code == 201
    shop = resp.json()
    return {"shop_id": uuid.UUID(shop["id"]), "shop": shop}


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
    product = await CatalogService.create_product(db_session, shop_id=shop.id, name="Inv Product", slug=f"inv-{uuid.uuid4().hex[:8]}", sku=f"INV-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    inventory = await InventoryService.initialize(db_session, shop_id=shop.id, product_id=product.id, initial_qty=__import__('decimal').Decimal("30.000"), created_by=owner.id)
    await db_session.commit()
    return product, inventory, shop, owner
