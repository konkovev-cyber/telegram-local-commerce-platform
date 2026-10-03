import uuid as _uuid


async def test_create_zone(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    slug = f"zone-{_uuid.uuid4().hex[:6]}"
    resp = await client.post("/api/v1/admin/geo/zones", headers=headers, json={"name": "Test Zone", "slug": slug})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Test Zone"
    assert data["slug"] == slug
    assert data["is_active"] is True
    zone_id = data["id"]

    # Get zone
    resp = await client.get(f"/api/v1/admin/geo/zones/{zone_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == zone_id

    # List zones
    resp = await client.get("/api/v1/admin/geo/zones", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Update zone
    resp = await client.patch(f"/api/v1/admin/geo/zones/{zone_id}", headers=headers, json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Delete zone
    resp = await client.delete(f"/api/v1/admin/geo/zones/{zone_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get(f"/api/v1/admin/geo/zones/{zone_id}", headers=headers)
    assert resp.status_code == 404


async def test_zone_slug_duplicate(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    slug = f"dup-{_uuid.uuid4().hex[:6]}"
    await client.post("/api/v1/admin/geo/zones", headers=headers, json={"name": "Zone 1", "slug": slug})
    resp = await client.post("/api/v1/admin/geo/zones", headers=headers, json={"name": "Zone 2", "slug": slug})
    assert resp.status_code in (409, 422)


async def test_zone_missing_fields_422(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/geo/zones", headers=headers, json={})
    assert resp.status_code == 422


async def test_other_shop_zone_forbidden(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    slug = f"other-{_uuid.uuid4().hex[:6]}"
    await client.post("/api/v1/admin/geo/zones", headers=headers_a, json={"name": "A Zone", "slug": slug})
    resp = await client.get("/api/v1/admin/geo/zones", headers=headers_b)
    ids_b = {z["id"] for z in resp.json()}
    resp = await client.get("/api/v1/admin/geo/zones", headers=headers_a)
    ids_a = {z["id"] for z in resp.json()}
    assert ids_b.isdisjoint(ids_a) or len(ids_b) == 0
