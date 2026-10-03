"""
Root test conftest — schema reset + alembic migrations ONCE per session.
All sub-conftests inherit from this via the _schema_setup fixture.
"""
import pytest
import pytest_asyncio
import subprocess
import os


TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_commerce_test"


@pytest.fixture(scope="session", autouse=True)
def _schema_setup():
    """Reset test database and apply migrations once before any test."""
    import subprocess as _sp
    # Terminate existing connections
    _sp.run(
        ["docker", "exec", "kvartal_postgres", "psql", "-U", "postgres",
         "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='telegram_commerce_test' AND pid <> pg_backend_pid()"],
        capture_output=True,
    )
    _sp.run(
        ["docker", "exec", "kvartal_postgres", "psql", "-U", "postgres",
         "-c", "DROP DATABASE IF EXISTS telegram_commerce_test"],
        capture_output=True,
    )
    _sp.run(
        ["docker", "exec", "kvartal_postgres", "psql", "-U", "postgres",
         "-c", "CREATE DATABASE telegram_commerce_test"],
        capture_output=True, check=True,
    )
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL
    result = _sp.run(
        ["poetry", "run", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=env,
        cwd="/root/telegram-local-commerce-platform/backend",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed:\n{result.stderr}")


@pytest_asyncio.fixture()
async def _shared_db_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass
    await engine.dispose()


from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.db import get_db


@pytest_asyncio.fixture()
async def client(_shared_db_session):
    async def override_get_db():
        yield _shared_db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
