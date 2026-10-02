"""
S1: JWT Security Tests
- Valid JWT → 200
- Expired JWT → 401
- Wrong signature → 401
- Malformed JWT → 401
- Wrong issuer → 401
- Wrong audience → 401
"""
import pytest
from datetime import timedelta
from jose import jwt as jose_jwt
from app.modules.auth.jwt import create_access_token, JWT_ISSUER, JWT_AUDIENCE
from app.core.config import settings


@pytest.mark.asyncio
async def test_valid_jwt(client, user_a):
    """Valid JWT with correct claims → 200."""
    resp = await client.get("/api/v1/auth/me", headers=user_a["auth_headers"])
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expired_jwt(client, user_a):
    """Expired JWT → 401."""
    token = create_access_token(
        data={"sub": str(user_a["user"].id)},
        expires_delta=timedelta(seconds=-10),
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_signature_jwt(client, user_a):
    """JWT signed with wrong key → 401."""
    token = jose_jwt.encode(
        {"sub": str(user_a["user"].id), "iss": JWT_ISSUER, "aud": JWT_AUDIENCE},
        "wrong-secret-key-that-is-definitely-not-correct",
        algorithm="HS256",
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_jwt(client):
    """Garbage string as JWT → 401."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_issuer_jwt(client, user_a):
    """JWT with wrong issuer → 401."""
    token = jose_jwt.encode(
        {"sub": str(user_a["user"].id), "iss": "wrong-issuer", "aud": JWT_AUDIENCE},
        settings.secret_key,
        algorithm="HS256",
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_audience_jwt(client, user_a):
    """JWT with wrong audience → 401."""
    token = jose_jwt.encode(
        {"sub": str(user_a["user"].id), "iss": JWT_ISSUER, "aud": "wrong-audience"},
        settings.secret_key,
        algorithm="HS256",
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_header(client):
    """Missing Authorization header → 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
