"""S2-A: Products — creation without prices, SKU/barcode constraints."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_create_product(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "Widget", "slug": "widget", "sku": "WDG-001", "tags": ["new"]
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Widget"
    assert data["sku"] == "WDG-001"
    assert "price" not in data  # No prices in S2-A


@pytest.mark.asyncio
async def test_create_product_with_category_and_unit(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    cat = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "Cat", "slug": "cat1"})
    unit = await client.post("/api/v1/admin/units", headers=headers, json={"name": "kg", "short_name": "кг"})
    resp = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "Prod", "slug": "prod1", "sku": "P-001",
        "category_id": cat.json()["id"], "unit_id": unit.json()["id"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["category_id"] == cat.json()["id"]
    assert data["unit_id"] == unit.json()["id"]


@pytest.mark.asyncio
async def test_product_sku_duplicate_409(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "A", "slug": "a", "sku": "SAME-SKU"
    })
    resp = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "B", "slug": "b", "sku": "SAME-SKU"
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_product_barcode_partial_unique(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "A", "slug": "a", "sku": "SKU-A", "barcode": "123456"
    })
    resp = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "B", "slug": "b", "sku": "SKU-B", "barcode": "123456"
    })
    assert resp.status_code == 409
    # Different barcodes allowed
    resp2 = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "C", "slug": "c", "sku": "SKU-C", "barcode": "654321"
    })
    assert resp2.status_code == 201
    # Null barcodes allowed (no partial unique)
    resp3 = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "D", "slug": "d", "sku": "SKU-D"
    })
    assert resp3.status_code == 201


@pytest.mark.asyncio
async def test_product_update(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    create_resp = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "Prod", "slug": "prod1", "sku": "P-001"
    })
    prod_id = create_resp.json()["id"]
    patch_resp = await client.patch(f"/api/v1/admin/products/{prod_id}", headers=headers, json={
        "name": "Updated", "is_active": False
    })
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated"
    assert patch_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_product_foreign_category_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_cat = await client.post("/api/v1/admin/categories", headers=headers_b, json={"name": "B", "slug": "b-cat"})
    resp = await client.post("/api/v1/admin/products", headers=headers_a, json={
        "name": "Prod", "slug": "prod-b-cat", "sku": "B-001",
        "category_id": b_cat.json()["id"],
    })
    assert resp.status_code == 403
