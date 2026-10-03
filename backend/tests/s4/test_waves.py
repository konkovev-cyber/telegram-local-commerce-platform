import uuid as _uuid
from datetime import date, datetime, timezone, timedelta

import pytest


async def test_create_wave(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "collecting"
    assert data["number"] == 1
    wave_id = data["id"]

    # Get wave
    resp = await client.get(f"/api/v1/admin/waves/{wave_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "collecting"

    # List waves
    resp = await client.get("/api/v1/admin/waves", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_wave_lifecycle(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    wave_id = resp.json()["id"]

    # collecting -> closed
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"

    # closed -> assembling
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/assemble", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "assembling"

    # assembling -> delivering
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/deliver", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "delivering"

    # delivering -> done
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/done", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


async def test_wave_invalid_transition(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    wave_id = resp.json()["id"]

    # Trying to go collecting -> assembling (skip closed)
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/assemble", headers=headers)
    assert resp.status_code == 400


async def test_wave_cancel(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    wave_id = resp.json()["id"]

    # Cancel from collecting
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/cancel", headers=headers, json={"reason": "Not enough orders"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # Cannot advance a cancelled wave
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/close", headers=headers)
    assert resp.status_code == 400


async def test_wave_time_slots(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/admin/waves", headers=headers, json={
        "zone_id": str(zone_a["zone_id"]),
        "delivery_date": tomorrow,
        "delivery_from": "10:00",
        "delivery_to": "20:00",
        "closes_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
    })
    wave_id = resp.json()["id"]

    # Create slots
    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/slots", headers=headers, json={
        "from_time": "10:00", "to_time": "14:00", "max_orders": 10,
    })
    assert resp.status_code == 201
    slot1_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/admin/waves/{wave_id}/slots", headers=headers, json={
        "from_time": "14:00", "to_time": "18:00", "max_orders": 10,
    })
    assert resp.status_code == 201

    # List slots
    resp = await client.get(f"/api/v1/admin/waves/{wave_id}/slots", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Delete slot
    resp = await client.delete(f"/api/v1/admin/waves/{wave_id}/slots/{slot1_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/admin/waves/{wave_id}/slots", headers=headers)
    assert len(resp.json()) == 1
