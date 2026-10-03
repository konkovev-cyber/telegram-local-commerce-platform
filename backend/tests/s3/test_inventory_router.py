"""S3: Inventory router — endpoints and tenant isolation."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_list_inventory_items(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.get("/api/v1/admin/inventory", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_get_inventory_item_404(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/admin/inventory/items/{fake_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_movements_404(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/admin/inventory/items/{fake_id}/movements", headers=headers)
    assert resp.status_code == 404
