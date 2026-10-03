"""S2-A: Concurrency test — 10 parallel POSTs for same SKU → 1 success / 9x 409."""
import asyncio
import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from app.modules.catalog.service import CatalogService

TEST_DB_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)


@pytest.mark.asyncio
async def test_concurrent_product_creation(user_a, shop_a):
    """Generate unique SKU once, then 10 concurrent creates with separate sessions."""
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    unique_sku = f"CONC-{uuid.uuid4().hex[:8]}"
    shop_id = shop_a["shop_id"]

    engine = create_async_engine(TEST_DB_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def create_product(i: int):
        session = Session()
        try:
            product = await CatalogService.create_product(
                session, shop_id=shop_id,
                name=f"Prod-{i}", slug=f"conc-{i}", sku=unique_sku,
            )
            await session.commit()
            return 201
        except Exception as e:
            await session.rollback()
            if "IntegrityError" in type(e).__name__ or "duplicate" in str(e).lower():
                return 409
            return 500
        finally:
            await session.close()
    await engine.dispose()

    tasks = [create_product(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    created = [r for r in results if r == 201]
    conflicts = [r for r in results if r == 409]
    others = [r for r in results if r not in (201, 409)]

    assert len(created) == 1, f"Expected 1 created, got {len(created)}: {results}"
    assert len(conflicts) == 9, f"Expected 9 conflicts, got {len(conflicts)}"
    assert len(others) == 0, f"Unexpected status codes: {others}"
