import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_004_reservations_schema_exists(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventory_reservations'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "inventory_id" in cols
    assert "qty" in cols
    assert "expires_at" in cols
    assert "status" in cols
