import pytest, uuid
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_012_all_tenant_tables_have_shop_id(db_session):
    TABLES = [
        "categories", "products", "product_variants", "prices",
        "inventory_items", "inventory_movements",
        "customers", "zones", "pickup_points", "waves",
        "orders", "payments", "campaigns", "analytics_events", "audit_logs",
    ]
    for table in TABLES:
        result = await db_session.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = :t AND column_name = 'shop_id'"),
            {"t": table},
        )
        assert result.fetchone() is not None, (
            f"INV-012 VIOLATION: Table '{table}' missing shop_id column."
        )
