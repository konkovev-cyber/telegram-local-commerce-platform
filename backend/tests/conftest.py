import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SEED_DATA', 'false')

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.database import Base, get_db
from app.models import User, Category, Tag, Entry, EntryTag, Attachment, EntryHistory
from app.services.auth import hash_password

TEST_DATABASE_URL = 'sqlite+aiosqlite:///:memory:'
test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(client):
    async with TestSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            user = User(username='admin', hashed_password=hash_password('admin'))
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user


@pytest.fixture
async def auth_token(client, admin_user):
    resp = await client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200, f'Login failed: {resp.text}'
    return resp.json()['access_token']


@pytest.fixture
async def authorized_client(client, auth_token):
    client.headers['Authorization'] = f'Bearer {auth_token}'
    return client
