import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_001_no_stock_qty_column_in_products(db_session):
    """Таблица products НЕ должна содержать колонку stock_qty."""
    result = await db_session.execute(
        text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'products' AND column_name = 'stock_qty'
        """)
    )
    assert len(result.fetchall()) == 0, (
        "INV-001 VIOLATION: Column 'stock_qty' found in 'products'. "
        "Inventory must be tracked via inventory_items + inventory_movements only."
    )
