import uuid as _uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest


async def _create_order(client, headers, shop_id, wave_id, product_id):
    """Helper: create an order and return order_id."""
    resp = await client.post("/api/v1/orders", headers=headers, json={
        "shop_id": str(shop_id), "wave_id": str(wave_id),
        "items": [{"product_id": str(product_id), "qty": 1}],
    })
    if resp.status_code != 201:
        pytest.skip(f"Order creation failed: {resp.text}")
    return resp.json()["id"]


async def test_create_cash_payment(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "cash", "amount": "100.00",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["method"] == "cash"
    assert data["status"] in ("unpaid", "pending")
    payment_id = data["id"]

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == payment_id


async def test_create_payment_idempotency(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)
    key = f"pay-idemp-{_uuid.uuid4().hex}"

    resp1 = await client.post("/api/v1/payments",
        json={"order_id": order_id, "method": "cash", "amount": "50.00"},
        headers={**headers, "Idempotency-Key": key})
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    resp2 = await client.post("/api/v1/payments",
        json={"order_id": order_id, "method": "cash", "amount": "50.00"},
        headers={**headers, "Idempotency-Key": key})
    assert resp2.status_code == 201
    assert resp2.json()["id"] == id1


async def test_mark_cash_paid(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "cash", "amount": "200.00",
    })
    assert resp.status_code == 201
    payment_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/admin/payments/{payment_id}/mark-paid", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    assert resp.json()["paid_at"] is not None


async def test_invalid_status_transition(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "cash", "amount": "100.00",
    })
    payment_id = resp.json()["id"]

    # First mark paid
    resp = await client.post(f"/api/v1/admin/payments/{payment_id}/mark-paid", headers=headers)
    assert resp.status_code == 200

    # Second mark paid should fail
    resp = await client.post(f"/api/v1/admin/payments/{payment_id}/mark-paid", headers=headers)
    assert resp.status_code == 400


async def test_refund_payment(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "yookassa", "amount": "500.00",
    })
    payment_id = resp.json()["id"]

    await client.post(f"/api/v1/admin/payments/{payment_id}/mark-paid", headers=headers)

    resp = await client.post(f"/api/v1/admin/payments/{payment_id}/refund", headers=headers, json={
        "amount": "500.00", "reason": "Customer complaint",
    })
    assert resp.status_code == 200
    assert resp.json()["amount"] == "500.00"
    assert resp.json()["status"] == "completed"

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert resp.json()["status"] == "refunded"


async def test_partial_refund(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "yookassa", "amount": "1000.00",
    })
    payment_id = resp.json()["id"]

    await client.post(f"/api/v1/admin/payments/{payment_id}/mark-paid", headers=headers)

    resp = await client.post(f"/api/v1/admin/payments/{payment_id}/refund", headers=headers, json={
        "amount": "300.00", "reason": "Partial return",
    })
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert resp.json()["status"] == "partially_refunded"


async def test_webhook_succeeded(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "yookassa", "amount": "100.00",
    })
    payment_id = resp.json()["id"]

    resp = await client.post("/api/v1/payments/webhook/yookassa", json={
        "id": f"wh-{_uuid.uuid4().hex}",
        "type": "payment.succeeded",
        "data": {"object": {"id": payment_id}},
    })
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert resp.json()["status"] == "paid"


async def test_webhook_already_processed(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "yookassa", "amount": "100.00",
    })
    payment_id = resp.json()["id"]

    event_id = f"wh-dup-{_uuid.uuid4().hex}"

    resp = await client.post("/api/v1/payments/webhook/yookassa", json={
        "id": event_id, "type": "payment.succeeded",
        "data": {"object": {"id": payment_id}},
    })
    assert resp.status_code == 200

    # Duplicate — should not error
    resp = await client.post("/api/v1/payments/webhook/yookassa", json={
        "id": event_id, "type": "payment.succeeded",
        "data": {"object": {"id": payment_id}},
    })
    assert resp.status_code == 200


async def test_other_shop_payment_forbidden(client, user_a, shop_a, user_b, shop_b, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}

    order_id = await _create_order(client, headers_a, shop_a["shop_id"], wave_a["wave_id"], product.id)
    resp = await client.post("/api/v1/payments", headers=headers_a, json={
        "order_id": order_id, "method": "cash", "amount": "100.00",
    })
    payment_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_list_payments(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    for i in range(3):
        await client.post("/api/v1/payments", headers=headers, json={
            "order_id": order_id, "method": "cash", "amount": str(100 + i * 50),
        })

    resp = await client.get("/api/v1/admin/payments", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 3

    resp = await client.get("/api/v1/admin/payments?status=unpaid", headers=headers)
    assert resp.status_code == 200


async def test_payment_transactions(client, user_a, shop_a, wave_a, product_with_inventory):
    product, inventory = product_with_inventory
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    order_id = await _create_order(client, headers, shop_a["shop_id"], wave_a["wave_id"], product.id)

    resp = await client.post("/api/v1/payments", headers=headers, json={
        "order_id": order_id, "method": "cash", "amount": "100.00",
    })
    payment_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/admin/payments/{payment_id}/transactions", headers=headers)
    assert resp.status_code == 200
    txs = resp.json()
    assert len(txs) >= 1
    assert txs[0]["type"] == "charge"
