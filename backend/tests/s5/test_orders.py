import uuid as _uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest


async def test_create_order_success(client, user_a, shop_a, product_with_inventory, zone_a, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]),
        "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 2}],
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "new"
    assert data["number"] == 1
    assert data["qr_code"].startswith("QR-")
    order_id = data["id"]

    resp = await client.get(f"/api/v1/admin/orders/{order_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["wave_id"] == str(wave_a["wave_id"])


async def test_create_order_idempotency(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    key = f"idemp-{_uuid.uuid4().hex}"

    resp1 = await client.post("/api/v1/orders",
        json={"shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
              "items": [{"product_id": str(product.id), "qty": 1}]},
        headers={**headers, "Idempotency-Key": key})
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    resp2 = await client.post("/api/v1/orders",
        json={"shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
              "items": [{"product_id": str(product.id), "qty": 1}]},
        headers={**headers, "Idempotency-Key": key})
    assert resp2.status_code == 201
    assert resp2.json()["id"] == id1


async def test_order_status_transitions(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    order_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/status", headers=headers,
                             json={"status": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/status", headers=headers,
                             json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_invalid_status_transition(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    order_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/status", headers=headers,
                             json={"status": "completed"})
    assert resp.status_code == 400


async def test_cancel_order_releases_inventory(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 5}],
    })
    order_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/admin/inventory/items/{inventory.id}", headers=headers)
    reserved_after = float(resp.json()["reserved_qty"])
    assert reserved_after >= 5

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    resp = await client.get(f"/api/v1/admin/inventory/items/{inventory.id}", headers=headers)
    reserved_after_cancel = float(resp.json()["reserved_qty"])
    assert reserved_after_cancel < reserved_after


async def test_cannot_order_closed_wave(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    assert resp.status_code == 400


async def test_order_qr_scan(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    qr_code = resp.json()["qr_code"]
    order_id = resp.json()["id"]

    resp = await client.post("/api/v1/admin/orders/qr/scan", headers=headers,
                             json={"qr_code": qr_code})
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id

    resp = await client.post("/api/v1/admin/orders/qr/scan", headers=headers,
                             json={"qr_code": "QR-INVALID"})
    assert resp.status_code == 404


async def test_other_shop_order_forbidden(client, user_a, shop_a, product_with_inventory, wave_a, user_b, shop_b):
    product, inventory = product_with_inventory
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers_a, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    order_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/admin/orders/{order_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_customer_list_my_orders(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = user_a["auth_headers"]

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    order_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/orders/my", params={"shop_id": str(shop_a["shop_id"])},
                            headers=headers)
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()]
    assert order_id in ids


async def test_order_number_unique_per_shop(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    assert resp.json()["number"] == 1

    resp2 = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    assert resp2.json()["number"] == 2


async def test_fulfillment_created_with_order(client, user_a, shop_a, product_with_inventory, wave_a):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_a["shop_id"]), "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    order_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/admin/orders/{order_id}/status-log", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert any(l["field"] == "order_status" and l["new_value"] == "new" for l in logs)


async def test_guest_order_success(client, shop_a, product_with_inventory, wave_a):
    """Guest order without auth token — uses phone number."""
    product, inventory = product_with_inventory
    phone = "+79991234567"
    resp = await client.post("/api/v1/orders", json={
        "shop_id": str(shop_a["shop_id"]),
        "wave_id": str(wave_a["wave_id"]),
        "customer_phone": phone,
        "customer_name": "Test Guest",
        "items": [{"product_id": str(product.id), "qty": 2}],
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "new"
    assert data["qr_code"].startswith("QR-")
    order_id = data["id"]

    # Should be retrievable by phone
    resp = await client.get(f"/api/v1/orders/by-phone", params={
        "phone": phone, "shop_id": str(shop_a["shop_id"])
    })
    assert resp.status_code == 200
    phones_orders = resp.json()
    assert len(phones_orders) >= 1
    assert any(o["id"] == order_id for o in phones_orders)

    # Should be retrievable by order_id + phone
    resp = await client.get(f"/api/v1/orders/by-phone/{order_id}", params={
        "phone": phone, "shop_id": str(shop_a["shop_id"])
    })
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id


async def test_guest_order_requires_phone(client, shop_a, product_with_inventory, wave_a):
    """Guest order without phone should fail."""
    product, inventory = product_with_inventory
    resp = await client.post("/api/v1/orders", json={
        "shop_id": str(shop_a["shop_id"]),
        "wave_id": str(wave_a["wave_id"]),
        "items": [{"product_id": str(product.id), "qty": 1}],
    })
    assert resp.status_code == 422


async def test_guest_order_by_phone_not_found(client, shop_a):
    """Phone with no orders returns empty list."""
    resp = await client.get("/api/v1/orders/by-phone", params={
        "phone": "+79990000000", "shop_id": str(shop_a["shop_id"])
    })
    assert resp.status_code == 200
    assert resp.json() == []
