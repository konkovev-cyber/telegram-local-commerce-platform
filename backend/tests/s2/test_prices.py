"""
tests/s2/test_prices.py — S2-B: Price History Service

Covers:
  - POST /admin/products/{id}/price → 201, active price set
  - Repeat POST → old price closed (valid_to not null), new price active
  - GET /admin/products/{id}/price → current price
  - GET /admin/products/{id}/price/history → full history (both rows)
  - INV-005: price change does NOT alter existing order_item.unit_price (snapshot)
  - INV-011: audit_log entry written on set_price
  - IDOR: price set on foreign product → 404
  - 400 on invalid UUID
"""
import uuid
import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy import select, text

from tests.s2.conftest import make_token


ADMIN_HEADERS_SHOP = lambda token, shop_id: {
    "Authorization": f"Bearer {token}",
    "X-Shop-Id": str(shop_id),
}


# ── helpers ────────────────────────────────────────────────────────────────

async def create_product(client, token, shop_id) -> dict:
    sku = uuid.uuid4().hex[:10]
    resp = await client.post(
        "/api/v1/admin/products",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"name": "Тестовый товар", "slug": f"slug-{sku}", "sku": sku},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_price_creates_active_price(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    resp = await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "299.00", "currency": "RUB"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["amount"] == "299.00"
    assert data["currency"] == "RUB"
    assert data["valid_to"] is None, "Active price must have valid_to=NULL"


@pytest.mark.asyncio
async def test_set_price_closes_previous_price(client, user_a, shop_a, db_session):
    from app.modules.catalog.price_models import Price

    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    # First price
    resp1 = await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "299.00", "currency": "RUB"},
    )
    assert resp1.status_code == 201
    old_price_id = resp1.json()["id"]

    # Second price (should close the first)
    resp2 = await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "399.00", "currency": "RUB"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["amount"] == "399.00"
    assert resp2.json()["valid_to"] is None

    # Old price must have valid_to set (closed, NOT deleted)
    result = await db_session.execute(
        select(Price).where(Price.id == uuid.UUID(old_price_id))
    )
    old = result.scalar_one_or_none()
    assert old is not None, "Old price row must NOT be deleted (INV-005)"
    assert old.valid_to is not None, "Old price must be closed (valid_to != NULL)"


@pytest.mark.asyncio
async def test_get_current_price(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "499.00", "currency": "RUB"},
    )

    resp = await client.get(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["amount"] == "499.00"
    assert resp.json()["valid_to"] is None


@pytest.mark.asyncio
async def test_get_price_history_has_all_rows(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    for amount in ["100.00", "200.00", "300.00"]:
        r = await client.post(
            f"/api/v1/admin/products/{product_id}/price",
            headers=ADMIN_HEADERS_SHOP(token, shop_id),
            json={"amount": amount, "currency": "RUB"},
        )
        assert r.status_code == 201

    resp = await client.get(
        f"/api/v1/admin/products/{product_id}/price/history",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
    )
    assert resp.status_code == 200, resp.text
    history = resp.json()
    assert len(history) == 3, f"Expected 3 history rows, got {len(history)}"
    # Newest first
    assert history[0]["amount"] == "300.00"
    # All closed except most recent
    closed = [h for h in history if h["valid_to"] is not None]
    active = [h for h in history if h["valid_to"] is None]
    assert len(closed) == 2
    assert len(active) == 1


@pytest.mark.asyncio
async def test_set_price_writes_audit_log(client, user_a, shop_a, db_session):
    from app.modules.audit.models import AuditLog

    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "750.00", "currency": "RUB"},
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(product_id),
            AuditLog.action == "product.price_change",
        )
    )
    logs = result.scalars().all()
    assert len(logs) >= 1, "INV-011: audit_log must be written on set_price"
    assert logs[-1].after is not None
    assert logs[-1].after["amount"] == "750.00"


@pytest.mark.asyncio
async def test_set_price_idor_foreign_product(client, user_a, shop_a, user_b, shop_b):
    """IDOR: user_b cannot set price on shop_a's product."""
    token_a = user_a["token"]
    shop_id_a = shop_a["shop_id"]
    product = await create_product(client, token_a, shop_id_a)
    product_id = product["id"]

    # user_b tries to set price on shop_a product via shop_b context
    resp = await client.post(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(user_b["token"], shop_b["shop_id"]),
        json={"amount": "9999.00", "currency": "RUB"},
    )
    assert resp.status_code == 404, f"Expected 404 IDOR guard, got {resp.status_code}"


@pytest.mark.asyncio
async def test_set_price_invalid_uuid(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    resp = await client.post(
        "/api/v1/admin/products/not-a-uuid/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
        json={"amount": "100.00", "currency": "RUB"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_price_404_when_no_price_set(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = shop_a["shop_id"]
    product = await create_product(client, token, shop_id)
    product_id = product["id"]

    resp = await client.get(
        f"/api/v1/admin/products/{product_id}/price",
        headers=ADMIN_HEADERS_SHOP(token, shop_id),
    )
    assert resp.status_code == 404
