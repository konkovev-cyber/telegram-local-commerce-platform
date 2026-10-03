"""S2-A: IDOR tests — all cross-tenant access vectors return 403."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_product_to_foreign_category_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_cat = await client.post("/api/v1/admin/categories", headers=headers_b, json={"name": "B", "slug": "b-cat"})
    resp = await client.post("/api/v1/admin/products", headers=headers_a, json={
        "name": "X", "slug": "x", "sku": "X-IDOR", "category_id": b_cat.json()["id"]
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_product_to_foreign_unit_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_unit = await client.post("/api/v1/admin/units", headers=headers_b, json={"name": "lb", "short_name": "фн"})
    resp = await client.post("/api/v1/admin/products", headers=headers_a, json={
        "name": "X", "slug": "x2", "sku": "X-IDOR2", "unit_id": b_unit.json()["id"]
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_variant_to_foreign_product_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_prod = await client.post("/api/v1/admin/products", headers=headers_b, json={
        "name": "B", "slug": "b", "sku": "B-VAR"
    })
    resp = await client.post(f"/api/v1/admin/products/{b_prod.json()['id']}/variants",
                              headers=headers_a, json={"name": "X", "sku": "X-VAR"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_category_to_foreign_parent_post_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_cat = await client.post("/api/v1/admin/categories", headers=headers_b, json={"name": "B", "slug": "b-parent"})
    resp = await client.post("/api/v1/admin/categories", headers=headers_a, json={
        "name": "Child", "slug": "child-of-b", "parent_id": b_cat.json()["id"]
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_category_to_foreign_parent_patch_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_cat = await client.post("/api/v1/admin/categories", headers=headers_b, json={"name": "B", "slug": "b-patch"})
    a_cat = await client.post("/api/v1/admin/categories", headers=headers_a, json={"name": "A", "slug": "a-patch"})
    resp = await client.patch(f"/api/v1/admin/categories/{a_cat.json()['id']}", headers=headers_a, json={
        "name": "A", "slug": "a-patch", "parent_id": b_cat.json()["id"]
    })
    assert resp.status_code == 403
