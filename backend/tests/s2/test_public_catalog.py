"""
tests/s2/test_public_catalog.py — S2-B: Public Vitrine

Covers:
  - GET /catalog/shops/{slug}/categories → active tree, no auth required
  - GET /catalog/shops/{slug}/products   → active products + current price
  - GET /catalog/shops/{slug}/products/{id} → product detail + price
  - Inactive products excluded from public catalog
  - Products from other shop not visible via cross-slug
  - category_id filter works
"""
import uuid
import pytest


async def setup_shop_with_data(client, user, shop) -> dict:
    """Create a category + 2 products with prices, return ids."""
    token = user["token"]
    shop_id = str(shop["shop_id"])
    headers = {"Authorization": f"Bearer {token}", "X-Shop-Id": shop_id}

    # Category
    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=headers,
        json={"name": "Молочные продукты", "slug": "molochka"},
    )
    assert cat_resp.status_code == 201, cat_resp.text
    cat_id = cat_resp.json()["id"]

    # Product 1 (active, with price)
    sku1 = uuid.uuid4().hex[:10]
    p1_resp = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={
            "name": "Молоко 1л", "slug": f"moloko-{sku1}", "sku": sku1,
            "category_id": cat_id,
        },
    )
    assert p1_resp.status_code == 201
    p1_id = p1_resp.json()["id"]

    pr1_resp = await client.post(
        f"/api/v1/admin/products/{p1_id}/price",
        headers=headers,
        json={"amount": "89.00", "currency": "RUB"},
    )
    assert pr1_resp.status_code == 201

    # Product 2 (active, with price)
    sku2 = uuid.uuid4().hex[:10]
    p2_resp = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"name": "Кефир 0.5л", "slug": f"kefir-{sku2}", "sku": sku2},
    )
    assert p2_resp.status_code == 201
    p2_id = p2_resp.json()["id"]

    pr2_resp = await client.post(
        f"/api/v1/admin/products/{p2_id}/price",
        headers=headers,
        json={"amount": "59.00", "currency": "RUB"},
    )
    assert pr2_resp.status_code == 201

    # Product 3 (inactive, should be hidden from public)
    sku3 = uuid.uuid4().hex[:10]
    p3_resp = await client.post(
        "/api/v1/admin/products",
        headers=headers,
        json={"name": "Скрытый продукт", "slug": f"hidden-{sku3}", "sku": sku3},
    )
    assert p3_resp.status_code == 201
    p3_id = p3_resp.json()["id"]
    # Deactivate
    await client.patch(
        f"/api/v1/admin/products/{p3_id}",
        headers=headers,
        json={"is_active": False},
    )

    return {
        "cat_id": cat_id, "p1_id": p1_id, "p2_id": p2_id, "p3_id": p3_id,
        "shop_slug": shop["shop"]["slug"],
    }


@pytest.mark.asyncio
async def test_public_category_tree_no_auth(client, user_a, shop_a):
    token = user_a["token"]
    shop_id = str(shop_a["shop_id"])
    headers = {"Authorization": f"Bearer {token}", "X-Shop-Id": shop_id}

    # Create categories
    await client.post(
        "/api/v1/admin/categories", headers=headers,
        json={"name": "Продукты питания", "slug": "food"},
    )

    shop_slug = shop_a["shop"]["slug"]
    # No Authorization header — public endpoint
    resp = await client.get(f"/api/v1/catalog/shops/{shop_slug}/categories")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert any(c["slug"] == "food" for c in data)


@pytest.mark.asyncio
async def test_public_products_list_with_price(client, user_a, shop_a):
    ctx = await setup_shop_with_data(client, user_a, shop_a)
    shop_slug = ctx["shop_slug"]

    resp = await client.get(f"/api/v1/catalog/shops/{shop_slug}/products")
    assert resp.status_code == 200, resp.text
    products = resp.json()

    # All returned must be active
    assert all(p["is_active"] for p in products)

    # Inactive product must not appear
    ids = {p["id"] for p in products}
    assert ctx["p3_id"] not in ids, "Inactive product must not appear in public catalog"

    # Products with price must have current_price populated
    with_price = [p for p in products if p["id"] in (ctx["p1_id"], ctx["p2_id"])]
    for p in with_price:
        assert p["current_price"] is not None, f"Product {p['id']} has no price"


@pytest.mark.asyncio
async def test_public_products_filter_by_category(client, user_a, shop_a):
    ctx = await setup_shop_with_data(client, user_a, shop_a)
    shop_slug = ctx["shop_slug"]
    cat_id = ctx["cat_id"]

    resp = await client.get(
        f"/api/v1/catalog/shops/{shop_slug}/products",
        params={"category_id": cat_id},
    )
    assert resp.status_code == 200, resp.text
    products = resp.json()
    # Only p1 has this category
    assert all(p["category_id"] == cat_id for p in products), \
        "Category filter must return only products in that category"


@pytest.mark.asyncio
async def test_public_product_detail(client, user_a, shop_a):
    ctx = await setup_shop_with_data(client, user_a, shop_a)
    shop_slug = ctx["shop_slug"]
    p1_id = ctx["p1_id"]

    resp = await client.get(f"/api/v1/catalog/shops/{shop_slug}/products/{p1_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == p1_id
    assert data["current_price"] is not None
    assert data["current_price"]["amount"] == "89.00"


@pytest.mark.asyncio
async def test_public_product_detail_inactive_returns_404(client, user_a, shop_a):
    ctx = await setup_shop_with_data(client, user_a, shop_a)
    shop_slug = ctx["shop_slug"]
    p3_id = ctx["p3_id"]

    resp = await client.get(f"/api/v1/catalog/shops/{shop_slug}/products/{p3_id}")
    assert resp.status_code == 404, "Inactive product must return 404 on public endpoint"


@pytest.mark.asyncio
async def test_public_product_cross_shop_isolation(client, user_a, shop_a, user_b, shop_b):
    """Product from shop_a must not be accessible via shop_b slug."""
    ctx_a = await setup_shop_with_data(client, user_a, shop_a)
    shop_b_slug = shop_b["shop"]["slug"]
    p1_id = ctx_a["p1_id"]

    resp = await client.get(f"/api/v1/catalog/shops/{shop_b_slug}/products/{p1_id}")
    assert resp.status_code == 404, \
        "Cross-shop product access must return 404"


@pytest.mark.asyncio
async def test_public_shop_not_found(client):
    resp = await client.get("/api/v1/catalog/shops/nonexistent-shop-xyz/products")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_product_price_shows_latest(client, user_a, shop_a):
    """Public vitrine always shows the most recent active price."""
    ctx = await setup_shop_with_data(client, user_a, shop_a)
    shop_slug = ctx["shop_slug"]
    p1_id = ctx["p1_id"]
    token = user_a["token"]
    shop_id = str(shop_a["shop_id"])
    headers = {"Authorization": f"Bearer {token}", "X-Shop-Id": shop_id}

    # Update price
    await client.post(
        f"/api/v1/admin/products/{p1_id}/price",
        headers=headers,
        json={"amount": "199.00", "currency": "RUB"},
    )

    resp = await client.get(f"/api/v1/catalog/shops/{shop_slug}/products/{p1_id}")
    assert resp.status_code == 200
    assert resp.json()["current_price"]["amount"] == "199.00", \
        "Public vitrine must show the latest active price"
