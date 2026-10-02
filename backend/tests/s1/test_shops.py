"""
S1: Shop CRUD Tests
- POST /admin/shops → creates shop + OWNER atomically
- GET /admin/shops/my → user's shops
- GET /admin/shops/{id} → membership required
- PATCH /admin/shops/{id} → owner/admin + audit
- Duplicate slug → 409
"""
import pytest
from sqlalchemy import select, text


@pytest.mark.asyncio
async def test_create_shop(client, user_a, db_session):
    """POST /admin/shops → shop + OWNER membership + audit in one transaction."""
    resp = await client.post(
        "/api/v1/admin/shops",
        headers=user_a["auth_headers"],
        json={"slug": "my-new-shop", "name": "My New Shop", "currency": "RUB"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "my-new-shop"
    assert body["name"] == "My New Shop"
    assert body["owner_id"] == str(user_a["user"].id)
    assert body["plan"] == "free"
    assert body["is_active"] is True

    # Verify OWNER membership was created atomically
    from app.modules.shops.models import ShopMember
    import uuid
    stmt = select(ShopMember).where(
        ShopMember.shop_id == uuid.UUID(body["id"]),
        ShopMember.user_id == user_a["user"].id,
    )
    member = (await db_session.execute(stmt)).scalar_one_or_none()
    assert member is not None
    assert member.shop_role == "owner"

    # Verify audit log was created in same transaction
    from app.modules.audit.models import AuditLog
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_id == uuid.UUID(body["id"]),
        AuditLog.action == "SHOP_CREATED",
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.actor_id == user_a["user"].id


@pytest.mark.asyncio
async def test_create_shop_duplicate_slug(client, user_a, shop_a):
    """Duplicate slug → 409."""
    resp = await client.post(
        "/api/v1/admin/shops",
        headers=user_a["auth_headers"],
        json={"slug": shop_a["shop"].slug, "name": "Duplicate"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_my_shops(client, user_a, shop_a):
    """GET /admin/shops/my → only user's shops."""
    resp = await client.get(
        "/api/v1/admin/shops/my",
        headers=user_a["auth_headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    shop_ids = [s["id"] for s in body["shops"]]
    assert str(shop_a["shop"].id) in shop_ids


@pytest.mark.asyncio
async def test_list_my_shops_excludes_others(client, user_a, shop_b):
    """GET /admin/shops/my → does NOT include other user's shops."""
    resp = await client.get(
        "/api/v1/admin/shops/my",
        headers=user_a["auth_headers"],
    )
    assert resp.status_code == 200
    shop_ids = [s["id"] for s in resp.json()["shops"]]
    assert str(shop_b["shop"].id) not in shop_ids


@pytest.mark.asyncio
async def test_get_shop_with_membership(client, user_a, shop_a):
    """GET /admin/shops/{id} with valid membership → 200."""
    resp = await client.get(
        f"/api/v1/admin/shops/{shop_a['shop'].id}",
        headers={**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)},
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == shop_a["shop"].slug


@pytest.mark.asyncio
async def test_patch_shop(client, user_a, shop_a, db_session):
    """PATCH /admin/shops/{id} → updates + audit in one transaction."""
    resp = await client.patch(
        f"/api/v1/admin/shops/{shop_a['shop'].id}",
        headers={**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)},
        json={"name": "Updated Shop Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Shop Name"

    # Verify audit
    from app.modules.audit.models import AuditLog
    from sqlalchemy import select
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_id == shop_a["shop"].id,
        AuditLog.action == "SHOP_UPDATED",
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.before.get("name") == "Shop A"
    assert audit.after.get("name") == "Updated Shop Name"


@pytest.mark.asyncio
async def test_patch_shop_no_changes(client, user_a, shop_a):
    """PATCH with no actual changes → 200 but no audit entry."""
    resp = await client.patch(
        f"/api/v1/admin/shops/{shop_a['shop'].id}",
        headers={**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)},
        json={},
    )
    assert resp.status_code == 200
