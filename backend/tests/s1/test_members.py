"""
S1: Members Tests
- Add member → authorized role only
- Remove member → authorized role only
- Cannot remove owner
- List members → membership required
- Audit on member mutations
"""
import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_add_member(client, user_a, user_b, shop_a, db_session):
    """Owner adds a member → 201 + audit."""
    resp = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers={**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)},
        json={"user_id": str(user_b["user"].id), "shop_role": "operator"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == str(user_b["user"].id)
    assert body["shop_role"] == "operator"

    # Verify audit
    from app.modules.audit.models import AuditLog
    audit_stmt = select(AuditLog).where(
        AuditLog.action == "MEMBER_ADDED",
        AuditLog.shop_id == shop_a["shop"].id,
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_add_member_duplicate(client, user_a, user_b, shop_a):
    """Adding same member twice → 409."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    body = {"user_id": str(user_b["user"].id), "shop_role": "operator"}

    resp1 = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers=headers, json=body,
    )
    # Second attempt
    resp2 = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers=headers, json=body,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_members(client, user_a, shop_a):
    """List members → includes owner."""
    resp = await client.get(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers={**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)},
    )
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) >= 1
    owner = [m for m in members if m["shop_role"] == "owner"]
    assert len(owner) == 1


@pytest.mark.asyncio
async def test_remove_member(client, user_a, user_b, shop_a, db_session):
    """Remove a member → 204 + audit."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}

    # First add user_b
    await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers=headers,
        json={"user_id": str(user_b["user"].id), "shop_role": "operator"},
    )

    # Now remove
    resp = await client.delete(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members/{user_b['user'].id}",
        headers=headers,
    )
    assert resp.status_code == 204

    # Verify audit
    from app.modules.audit.models import AuditLog
    audit_stmt = select(AuditLog).where(
        AuditLog.action == "MEMBER_REMOVED",
        AuditLog.shop_id == shop_a["shop"].id,
    )
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_cannot_remove_owner(client, user_a, shop_a):
    """Cannot remove the owner → 403."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    resp = await client.delete(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members/{user_a['user'].id}",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_add_member(client, user_a, user_b, shop_a):
    """Operator role cannot add members → 403."""
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}

    # Add user_b as operator first
    await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers=headers_a,
        json={"user_id": str(user_b["user"].id), "shop_role": "operator"},
    )

    # Now user_b (operator) tries to add someone — create a third user inline
    from app.modules.auth.service import UserService
    from app.modules.auth.jwt import create_access_token

    # user_b tries to add via their own token
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    resp = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/members",
        headers=headers_b,
        json={"user_id": str(user_a["user"].id), "shop_role": "operator"},
    )
    assert resp.status_code == 403
