import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_003_inventory_movements_table_exists(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventory_movements'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "inventory_id" in cols
    assert "type" in cols
    assert "qty" in cols
    assert "before_available" in cols
    assert "after_available" in cols
