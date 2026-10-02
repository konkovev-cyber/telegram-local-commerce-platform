"""
S1: Telegram Auth Tests
- Valid initData → JWT
- Invalid HMAC → 401
- Expired auth_date → 401
- Modified user data → 401
- Missing hash → 401
- Malformed data → 401
- Repeated login → same user
- GET /auth/me → user profile
"""
import time
import json
import pytest
from tests.s1.conftest import make_telegram_init_data


@pytest.mark.asyncio
async def test_telegram_login_valid(client):
    """Valid Telegram initData → 200 + JWT + user_id."""
    user_data = {"id": 999001, "first_name": "TestUser"}
    init_data = make_telegram_init_data(user_data)

    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user_id"]  # UUID string
    assert body["is_new_user"] is True


@pytest.mark.asyncio
async def test_telegram_login_repeated_same_user(client):
    """Repeated login with same telegram_id → same user, not a duplicate."""
    user_data = {"id": 999002, "first_name": "Repeat"}
    init_data_1 = make_telegram_init_data(user_data)
    init_data_2 = make_telegram_init_data(user_data)

    resp1 = await client.post("/api/v1/auth/telegram", json={"init_data": init_data_1})
    resp2 = await client.post("/api/v1/auth/telegram", json={"init_data": init_data_2})

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["user_id"] == resp2.json()["user_id"]
    assert resp2.json()["is_new_user"] is False


@pytest.mark.asyncio
async def test_telegram_login_invalid_hmac(client):
    """Invalid HMAC signature → 401."""
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": "hash=invalid_hash_value&user={\"id\":1}&auth_date=9999999999"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_telegram_login_expired_auth_date(client):
    """auth_date older than 1 hour → 401."""
    user_data = {"id": 999003, "first_name": "Expired"}
    two_hours_ago = int(time.time()) - 7200
    init_data = make_telegram_init_data(user_data, auth_date=two_hours_ago)

    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_telegram_login_missing_hash(client):
    """initData without hash field → 401."""
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": "user={\"id\":1}&auth_date=9999999999"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_telegram_login_malformed_data(client):
    """Completely malformed initData → 401."""
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": "not_valid_data"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_telegram_login_modified_user_data(client):
    """Valid HMAC but tampered user data → 401."""
    user_data = {"id": 999004, "first_name": "Original"}
    init_data = make_telegram_init_data(user_data)
    # Tamper: replace the user JSON in the init_data string
    tampered = init_data.replace("Original", "Tampered")
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": tampered})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_valid(client, user_a):
    """GET /auth/me with valid JWT → user profile."""
    resp = await client.get("/api/v1/auth/me", headers=user_a["auth_headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(user_a["user"].id)
    assert body["first_name"] == "Alice"
    assert body["platform_role"] == "user"
