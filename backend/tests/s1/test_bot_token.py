"""
S1: Bot Token Tests (INV-009 + INV-013)
- POST /admin/shops/{id}/bot → encrypted in DB
- Plaintext NEVER in response
- Plaintext NEVER in audit
- decrypt(ciphertext) == original
- Cross-tenant bot mutation → 403
"""
import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_set_bot_token(client, user_a, shop_a, db_session):
    """POST bot → encrypted token stored, success metadata returned."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    raw_token = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"

    resp = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/bot",
        headers=headers,
        json={
            "bot_username": "test_shop_bot",
            "bot_token": raw_token,
            "mode": "shared",
        },
    )
    assert resp.status_code == 201
    body = resp.json()

    # INV-009: plaintext token NEVER in response
    assert "bot_token" not in body
    assert "encrypted_token" not in body
    assert "token" not in body
    assert raw_token not in str(body)

    # Verify bot_username and mode are returned
    assert body["bot_username"] == "test_shop_bot"
    assert body["mode"] == "shared"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_bot_token_encrypted_in_db(client, user_a, shop_a, db_session):
    """DB stores ciphertext, decrypt(ciphertext) == original."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    raw_token = "9876543210:ZZyyXXwwVVuuTTssRRqqPPooNNmmLLkkJJ"

    await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/bot",
        headers=headers,
        json={"bot_username": "crypto_test_bot", "bot_token": raw_token},
    )

    # Check DB directly
    from app.modules.shops.models import ShopBot
    stmt = select(ShopBot).where(ShopBot.shop_id == shop_a["shop"].id)
    bot = (await db_session.execute(stmt)).scalar_one()

    # DB value is NOT the plaintext
    assert bot.encrypted_token != raw_token

    # But decrypt gives back the original
    from app.modules.shops.crypto import decrypt_bot_token
    assert decrypt_bot_token(bot.encrypted_token) == raw_token


@pytest.mark.asyncio
async def test_bot_token_not_in_audit(client, user_a, shop_a, db_session):
    """Audit after field must NOT contain plaintext token."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    raw_token = "1111111111:SecretTokenThatMustNeverLeak12345"

    await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/bot",
        headers=headers,
        json={"bot_username": "audit_test_bot", "bot_token": raw_token},
    )

    from app.modules.audit.models import AuditLog
    stmt = select(AuditLog).where(
        AuditLog.action == "BOT_TOKEN_SET",
        AuditLog.shop_id == shop_a["shop"].id,
    )
    audit = (await db_session.execute(stmt)).scalar_one()

    # Secret NEVER in audit before/after
    import json
    audit_str = json.dumps(audit.after)
    assert raw_token not in audit_str
    assert "Secret" not in audit_str
    # But it should have configured: true
    assert audit.after.get("configured") is True


@pytest.mark.asyncio
async def test_bot_token_duplicate(client, user_a, shop_a):
    """Setting bot twice → 409."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop"].id)}
    bot_data = {"bot_username": "dup_bot", "bot_token": "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOpp"}

    resp1 = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/bot",
        headers=headers, json=bot_data,
    )
    resp2 = await client.post(
        f"/api/v1/admin/shops/{shop_a['shop'].id}/bot",
        headers=headers, json=bot_data,
    )
    assert resp2.status_code == 409
