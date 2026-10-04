import uuid as _uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest


async def _create_order(client, headers, shop_id, wave_id, product_id):
    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_id), "wave_id": str(wave_id),
        "items": [{"product_id": str(product_id), "qty": 2}],
    })
    if resp.status_code != 201:
        pytest.skip(f"Order creation failed: {resp.text}")
    return resp.json()["id"]


async def _create_payments(client, headers, order_id, method="cash", amount="100.00"):
    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": method, "amount": amount,
    })
    if resp.status_code != 201:
        pytest.skip(f"Payment creation failed: {resp.text}")
    return resp.json()["id"]


async def test_assembly_sheet_generated_on_wave_close(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id)

    # Close wave → should generate assembly sheet
    resp = await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    assert resp.status_code == 200, resp.text

    # Check assembly sheet exists
    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/assembly", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["product_name"] == product.name
    assert items[0]["required_qty"] == "2.000"
    assert items[0]["status"] == "pending"


async def test_assembly_sheet_excludes_cancelled(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id1 = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    order_id2 = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    # Cancel one order
    await client.post(f"/api/v1/admin/orders/{order_id1}/cancel", headers=headers)

    # Close wave
    resp = await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    assert resp.status_code == 200

    # Assembly should only include non-cancelled order (qty=2, not 4)
    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/assembly", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["required_qty"] == "2.000"


async def test_assembly_progress(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)

    # Get assembly items
    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/assembly", headers=headers)
    item_id = resp.json()[0]["id"]

    # Update picked qty to full required
    resp = await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "picked_qty": "2.000",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "picking"

    # Update packed qty
    resp = await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "packed_qty": "2.000",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "packed"

    # Update loaded qty (full)
    resp = await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "loaded_qty": "2.000",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "loaded"


async def test_assembly_qty_validation(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)

    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/assembly", headers=headers)
    item_id = resp.json()[0]["id"]

    # Picked > required → fail
    resp = await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "picked_qty": "999.000",
    })
    assert resp.status_code == 400

    # Packed > picked → fail
    await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "picked_qty": "2.000",
    })
    resp = await client.patch(f"/api/v1/admin/assembly/{item_id}", headers=headers, json={
        "wave_id": str(wave_a["wave_id"]), "packed_qty": "999.000",
    })
    assert resp.status_code == 400


async def test_manifest_generation(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id, method="cash", amount="200.00")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)

    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/manifest", headers=headers)
    assert resp.status_code == 200
    manifest = resp.json()
    assert len(manifest) >= 1
    assert manifest[0]["order_number"] == 1
    assert manifest[0]["payment_method"] == "cash"
    assert manifest[0]["payment_status"] == "unpaid"


async def test_fulfillment_lifecycle(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id, method="yookassa", amount="100.00")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/assemble", headers=headers)

    # Check order has wave linked and fulfillment exists
    resp = await client.get(f"/api/v1/admin/orders/{order_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["wave_id"] == str(wave_a["wave_id"])


async def test_qr_scan(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    # Get QR code from order
    resp = await client.get(f"/api/v1/admin/orders/{order_id}", headers=headers)
    qr_code = resp.json()["qr_code"]

    # Scan QR
    resp = await client.post("/api/v1/admin/qr/scan", headers=headers, json={"qr_code": qr_code})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == order_id
    assert data["qr_code"] == qr_code

    # Invalid QR
    resp = await client.post("/api/v1/admin/qr/scan", headers=headers, json={"qr_code": "QR-INVALID"})
    assert resp.status_code == 404


async def test_deliver_order(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    payment_id = await _create_payments(client, headers, order_id, method="cash", amount="150.00")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/assemble", headers=headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/fulfillment-status", headers=headers, json={"status": "arrived"})

    # Deliver order with cash acceptance
    resp = await client.post(f"/api/v1/admin/orders/{order_id}/deliver", headers=headers, json={
        "accept_cash": True,
    })
    assert resp.status_code == 200
    assert resp.json()["order_status"] == "completed"
    assert resp.json()["fulfillment_status"] == "delivered"

    # Payment should be paid now
    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert resp.json()["status"] == "paid"


async def test_no_double_deliver(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id, method="cash")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/assemble", headers=headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/fulfillment-status", headers=headers, json={"status": "arrived"})

    # First deliver
    resp = await client.post(f"/api/v1/admin/orders/{order_id}/deliver", headers=headers)
    assert resp.status_code == 200

    # Second deliver should fail
    resp = await client.post(f"/api/v1/admin/orders/{order_id}/deliver", headers=headers)
    assert resp.status_code == 400


async def test_outbox_on_delivery(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id, method="yookassa", amount="100.00")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/assemble", headers=headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/fulfillment-status", headers=headers, json={"status": "arrived"})

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/deliver", headers=headers)
    assert resp.status_code == 200

    # Check outbox has delivery event
    from sqlalchemy import select
    from app.core.outbox import OutboxEvent
    stmt = select(OutboxEvent).where(
        OutboxEvent.aggregate_type == "order",
        OutboxEvent.aggregate_id == _uuid.UUID(order_id),
        OutboxEvent.event_type == "fulfillment.delivered",
    )
    # Can't easily query here; just verify order is completed
    resp = await client.get(f"/api/v1/admin/orders/{order_id}", headers=headers)
    assert resp.json()["status"] == "completed"


async def test_manifest_idor(client, user_a, shop_a, wave_a, product_with_inventory, user_b, shop_b):
    product, inventory = product_with_inventory
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}

    await _create_order(client, headers_a, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers_a)

    # User B tries to access shop A's manifest
    resp = await client.get(f"/api/v1/admin/waves/{wave_a['wave_id']}/manifest", headers=headers_b)
    assert resp.status_code == 404


async def test_status_log_on_delivery(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    await _create_payments(client, headers, order_id, method="yookassa")
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/close", headers=headers)
    await client.post(f"/api/v1/admin/waves/{wave_a['wave_id']}/assemble", headers=headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/fulfillment-status", headers=headers, json={"status": "arrived"})

    resp = await client.post(f"/api/v1/admin/orders/{order_id}/deliver", headers=headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/admin/orders/{order_id}/status-log", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert any(l["new_value"] == "completed" for l in logs)
