"""S2-A: Product Variants — shop-wide SKU, cascade, barcode."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_create_variant(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    prod = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "Prod", "slug": "p", "sku": "P-001"
    })
    resp = await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                              headers=headers, json={"name": "Red", "sku": "RED-001", "qty_value": 1.5})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Red"
    assert data["sku"] == "RED-001"
    assert data["qty_value"] == 1.5
    assert data["product_id"] == prod.json()["id"]


@pytest.mark.asyncio
async def test_variant_sku_duplicate_409(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    prod = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "P", "slug": "p", "sku": "X-001"
    })
    await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                       headers=headers, json={"name": "V1", "sku": "VAR-SAME"})
    resp = await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                              headers=headers, json={"name": "V2", "sku": "VAR-SAME"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_variant_barcode_partial_unique(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    prod = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "P", "slug": "p", "sku": "B-001"
    })
    await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                       headers=headers, json={"name": "V1", "sku": "VAR-A", "barcode": "BC-100"})
    resp = await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                              headers=headers, json={"name": "V2", "sku": "VAR-B", "barcode": "BC-100"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_variants(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    prod = await client.post("/api/v1/admin/products", headers=headers, json={
        "name": "P", "slug": "p", "sku": "L-001"
    })
    await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                       headers=headers, json={"name": "V1", "sku": "VL-1"})
    await client.post(f"/api/v1/admin/products/{prod.json()['id']}/variants",
                       headers=headers, json={"name": "V2", "sku": "VL-2"})
    resp = await client.get(f"/api/v1/admin/products/{prod.json()['id']}/variants", headers=headers)
    assert resp.status_code == 200
    variants = resp.json()
    assert len(variants) == 2


@pytest.mark.asyncio
async def test_variant_foreign_product_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_prod = await client.post("/api/v1/admin/products", headers=headers_b, json={
        "name": "B", "slug": "b", "sku": "B-001"
    })
    resp = await client.post(f"/api/v1/admin/products/{b_prod.json()['id']}/variants",
                              headers=headers_a, json={"name": "X", "sku": "X-001"})
    assert resp.status_code == 403
