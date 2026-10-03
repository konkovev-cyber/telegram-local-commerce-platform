"""S2-A: Units CRUD, tenant isolation, 409 on duplicates."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_create_unit(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/units", headers=headers, json={"name": "kg", "short_name": "кг"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "kg"
    assert data["short_name"] == "кг"
    unit_id = data["id"]

    # GET list
    resp = await client.get("/api/v1/admin/units", headers=headers)
    assert resp.status_code == 200
    units = resp.json()
    assert len(units) >= 1
    assert any(u["id"] == unit_id for u in units)


@pytest.mark.asyncio
async def test_unit_409_duplicate_name(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await client.post("/api/v1/admin/units", headers=headers, json={"name": "шт", "short_name": "шт"})
    resp = await client.post("/api/v1/admin/units", headers=headers, json={"name": "шт", "short_name": "шт2"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unit_409_duplicate_short_name(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await client.post("/api/v1/admin/units", headers=headers, json={"name": "шт", "short_name": "шт"})
    resp = await client.post("/api/v1/admin/units", headers=headers, json={"name": "грамм", "short_name": "шт"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unit_tenant_isolation(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    await client.post("/api/v1/admin/units", headers=headers_a, json={"name": "kg", "short_name": "кг"})
    resp_b = await client.get("/api/v1/admin/units", headers=headers_b)
    units_b = resp_b.json()
    names_b = [u["name"] for u in units_b]
    assert "kg" not in names_b
