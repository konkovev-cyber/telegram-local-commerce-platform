"""
S1: IDOR / Tenant Isolation Tests (INV-012 + INV-013)

X-Shop-Id is a SELECTOR, never authority.
Backend MUST: JWT → user → shop_members → authorized shop.

All cross-tenant access vectors:
    User A + X-Shop-Id=Shop_B         → 403
    User A + path /shops/Shop_B/...   → 403
    User A + body.shop_id=Shop_B      → 403
    Shop A user → Shop B operations   → 403
"""
import pytest
import uuid


@pytest.mark.asyncio
async def test_idor_header_shop_get(client, user_a, shop_b):
    """
    User A + X-Shop-Id=Shop_B → 403.
    X-Shop-Id alone NEVER grants access.
    """
    resp = await client.get(
        f"/api/v1/admin/shops/{shop_b['shop'].id}",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idor_header_shop_patch(client, user_a, shop_b):
    """User A tries to PATCH Shop B → 403."""
    resp = await client.patch(
        f"/api/v1/admin/shops/{shop_b['shop'].id}",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
        json={"name": "Hacked Name"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idor_header_members_list(client, user_a, shop_b):
    """User A tries to list Shop B members → 403."""
    resp = await client.get(
        f"/api/v1/admin/shops/{shop_b['shop'].id}/members",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idor_header_member_add(client, user_a, user_b, shop_b):
    """User A tries to add member to Shop B → 403."""
    resp = await client.post(
        f"/api/v1/admin/shops/{shop_b['shop'].id}/members",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
        json={"user_id": str(user_a["user"].id), "shop_role": "admin"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idor_header_bot_set(client, user_a, shop_b):
    """User A tries to set bot on Shop B → 403."""
    resp = await client.post(
        f"/api/v1/admin/shops/{shop_b['shop'].id}/bot",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
        json={
            "bot_username": "hacked_bot",
            "bot_token": "1234567890:HackedTokenAttempt00000000000000",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idor_nonexistent_shop(client, user_a):
    """Access to a non-existent shop → 404."""
    fake_shop_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/admin/shops/{fake_shop_id}",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": fake_shop_id,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_idor_member_remove_cross_tenant(client, user_a, user_b, shop_b):
    """User A tries to remove User B from Shop B → 403."""
    resp = await client.delete(
        f"/api/v1/admin/shops/{shop_b['shop'].id}/members/{user_b['user'].id}",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_b["shop"].id),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_my_shops_never_leaks_other_shops(client, user_a, shop_a, shop_b):
    """GET /admin/shops/my never returns shops user is not a member of."""
    resp = await client.get(
        "/api/v1/admin/shops/my",
        headers=user_a["auth_headers"],
    )
    assert resp.status_code == 200
    shop_ids = [s["id"] for s in resp.json()["shops"]]
    assert str(shop_b["shop"].id) not in shop_ids
    # User A's shop should be present
    assert str(shop_a["shop"].id) in shop_ids


@pytest.mark.asyncio
async def test_shop_response_never_contains_bot_token(client, user_a, shop_a):
    """Full response body of GET shop → no token leak."""
    resp = await client.get(
        f"/api/v1/admin/shops/{shop_a['shop'].id}",
        headers={
            **user_a["auth_headers"],
            "X-Shop-Id": str(shop_a["shop"].id),
        },
    )
    assert resp.status_code == 200
    resp_text = resp.text
    assert "bot_token" not in resp_text
    assert "encrypted_token" not in resp_text
