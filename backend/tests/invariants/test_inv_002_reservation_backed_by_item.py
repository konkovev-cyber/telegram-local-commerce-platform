import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_002_no_orphaned_reservations(db_session):
    result = await db_session.execute(
        text("""
            SELECT ir.id FROM inventory_reservations ir
            LEFT JOIN inventory_items ii ON ii.id = ir.inventory_id
            WHERE ii.id IS NULL
        """)
    )
    orphans = result.fetchall()
    assert len(orphans) == 0, (
        f"INV-002 VIOLATION: {len(orphans)} orphaned reservations without inventory_item."
    )
