import uuid as _uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest


async def test_create_campaign(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={
        "name": "Summer Sale 2026",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Summer Sale 2026"
    assert data["is_active"] is True
    campaign_id = data["id"]

    # Get campaign
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Summer Sale 2026"

    # List campaigns
    resp = await client.get("/api/v1/admin/campaigns", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Update campaign
    resp = await client.patch(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers, json={
        "is_active": False,
    })
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_campaign_idor(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}

    # Create campaign in shop A
    resp = await client.post("/api/v1/admin/campaigns", headers=headers_a, json={"name": "Shop A Campaign"})
    assert resp.status_code == 201
    campaign_id = resp.json()["id"]

    # User B cannot access shop A's campaign
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_create_source_with_deep_link(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={"name": "Test Campaign"})
    campaign_id = resp.json()["id"]

    ref_code = f"solnechny-{_uuid.uuid4().hex[:4]}"
    resp = await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": "Solar District",
        "ref_code": ref_code,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["ref_code"] == ref_code
    assert data["deep_link"].startswith("https://t.me/")
    assert f"ref_{ref_code}" in data["deep_link"]


async def test_ref_code_unique(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={"name": "Campaign 1"})
    campaign_id = resp.json()["id"]

    ref_code = f"dup-{_uuid.uuid4().hex[:6]}"
    await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": "Source 1", "ref_code": ref_code,
    })
    # Duplicate ref_code should fail
    resp = await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": "Source 2", "ref_code": ref_code,
    })
    assert resp.status_code in (409, 422)


async def test_resolve_ref_code(client, user_a, shop_a, zone_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={"name": "Ref Campaign"})
    campaign_id = resp.json()["id"]
    ref_code = f"resolve-{_uuid.uuid4().hex[:6]}"

    await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": "Resolved Source", "ref_code": ref_code, "zone_id": str(zone_a["zone_id"]),
    })

    # Verify deep link format
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers)
    sources = resp.json()["sources"]
    assert len(sources) >= 1
    found = [s for s in sources if s["ref_code"] == ref_code]
    assert len(found) == 1
    assert found[0]["deep_link"] is not None


async def test_analytics_session_creation(client, user_a):
    headers = user_a["auth_headers"]
    customer_id = _uuid.uuid4()

    resp = await client.post("/api/v1/analytics/session", json={
        "customer_id": str(customer_id),
        "ref_code": "test-ref",
        "platform": "android",
        "utm_source": "telegram",
        "utm_medium": "cpc",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["ref_code"] == "test-ref"


async def test_track_event(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    # Create session first
    resp = await client.post("/api/v1/analytics/session", json={
        "shop_id": str(shop_a["shop_id"]),
        "platform": "ios",
    })
    session_id = resp.json()["id"]

    # Track an event
    resp = await client.post("/api/v1/analytics/event", json={
        "shop_id": str(shop_a["shop_id"]),
        "session_id": session_id,
        "event_name": "product_view",
        "entity_type": "product",
        "entity_id": str(_uuid.uuid4()),
        "metadata": {"product_name": "Test Product"},
    })
    assert resp.status_code == 204


async def test_campaign_funnel(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}

    # Create campaign with source
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={"name": "Funnel Test"})
    campaign_id = resp.json()["id"]
    ref_code = f"funnel-{_uuid.uuid4().hex[:6]}"
    await client.post(f"/api/v1/admin/campaigns/{campaign_id}/sources", headers=headers, json={
        "name": "Funnel Source", "ref_code": ref_code,
    })

    # Create session and track events
    resp = await client.post("/api/v1/analytics/session", json={
        "shop_id": str(shop_a["shop_id"]), "ref_code": ref_code,
    })
    session_id = resp.json()["id"]

    # Track funnel events
    for event_name in ["campaign_click", "app_open", "add_to_cart", "order_created"]:
        await client.post("/api/v1/analytics/event", json={
            "shop_id": str(shop_a["shop_id"]),
            "session_id": session_id,
            "event_name": event_name,
            "metadata": {"total": "100.00"} if event_name == "order_created" else {},
        })

    # Get funnel
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_id}/funnel", headers=headers)
    assert resp.status_code == 200
    funnel = resp.json()
    assert len(funnel) >= 1
    assert funnel[0]["clicks"] >= 1
    assert funnel[0]["opens"] >= 1
    assert funnel[0]["carts"] >= 1
    assert funnel[0]["orders"] >= 1


async def test_isolated_analytics_between_shops(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}

    # Shop A creates campaign and tracks events
    resp = await client.post("/api/v1/admin/campaigns", headers=headers_a, json={"name": "Shop A Campaign"})
    campaign_a_id = resp.json()["id"]
    ref_a = f"shopa-{_uuid.uuid4().hex[:6]}"
    await client.post(f"/api/v1/admin/campaigns/{campaign_a_id}/sources", headers=headers_a, json={
        "name": "Source A", "ref_code": ref_a,
    })
    resp = await client.post("/api/v1/analytics/session", json={
        "shop_id": str(shop_a["shop_id"]), "ref_code": ref_a,
    })
    session_a = resp.json()["id"]
    await client.post("/api/v1/analytics/event", json={
        "shop_id": str(shop_a["shop_id"]), "session_id": session_a,
        "event_name": "campaign_click",
    })

    # Shop B creates different campaign
    resp = await client.post("/api/v1/admin/campaigns", headers=headers_b, json={"name": "Shop B Campaign"})
    campaign_b_id = resp.json()["id"]

    # Shop B's funnel should not include Shop A's data
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_b_id}/funnel", headers=headers_b)
    assert resp.status_code == 200
    funnel_b = resp.json()
    # Shop B has no events, so funnel should be empty or have zero counts
    for item in funnel_b:
        assert item["clicks"] == 0


async def test_campaign_delete(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/campaigns", headers=headers, json={"name": "ToDelete"})
    campaign_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get(f"/api/v1/admin/campaigns/{campaign_id}", headers=headers)
    assert resp.status_code == 404
