import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_005_order_items_schema_has_full_snapshot_fields(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'order_items'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "product_name" in cols, "INV-005 VIOLATION: order_items missing product_name snapshot"
    assert "unit_price" in cols, "INV-005 VIOLATION: order_items missing unit_price snapshot"
    assert "cost_price" in cols, "INV-005 VIOLATION: order_items missing cost_price snapshot"
