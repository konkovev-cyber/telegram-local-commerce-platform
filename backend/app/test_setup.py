import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-development-only")

from app.main import app
from app.database import get_db, init_db
from app.services.entries import seed_categories, seed_entries
from app.models import User
from app.services.auth import hash_password
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

test_engine = create_async_engine(DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

async def override_get_db():
    async with TestSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

app.dependency_overrides[get_db] = override_get_db
