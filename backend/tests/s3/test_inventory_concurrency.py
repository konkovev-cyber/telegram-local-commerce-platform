"""S3: Inventory concurrency — INV-004 stress test."""
import asyncio
import pytest
import uuid
from decimal import Decimal
from sqlalchemy import select


@pytest.mark.asyncio
async def test_concurrent_reserve_no_oversell(db_session, shop_and_owner):
    """10 concurrent reserves on qty=1 → exactly 1 success, 9 failures."""
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService, InsufficientStockError
    from app.modules.inventory.models import InventoryItem

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Conc Test", slug="conc-test", sku=f"CONC-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("1.000"), created_by=owner.id,
    )
    await db_session.commit()
    inventory_id = item.id

    async def try_reserve(i: int):
        try:
            await InventoryService.reserve(
                db_session, inventory_id=inventory_id, qty=Decimal("1.000"),
                order_id=None, ttl_minutes=15,
            )
            return 201
        except InsufficientStockError:
            return 409
        except Exception:
            return 500

    results = await asyncio.gather(*[try_reserve(i) for i in range(10)])
    created = [r for r in results if r == 201]
    conflicts = [r for r in results if r == 409]
    errors = [r for r in results if r not in (201, 409)]

    assert len(created) == 1, f"Expected 1 success, got {len(created)}: {results}"
    assert len(conflicts) == 9, f"Expected 9 conflicts, got {len(conflicts)}"
    assert len(errors) == 0, f"Unexpected errors: {errors}"

    # Verify DB state
    updated = await db_session.get(InventoryItem, inventory_id)
    await db_session.commit()
    assert updated.available_qty == Decimal("0.000"), (
        f"INV-004 VIOLATION: available_qty={updated.available_qty}, expected 0"
    )
    assert updated.reserved_qty == Decimal("1.000"), (
        f"INV-004 VIOLATION: reserved_qty={updated.reserved_qty}, expected 1"
    )
