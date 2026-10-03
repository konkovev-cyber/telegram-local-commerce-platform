"""S3: Inventory service — reserve, sell, release, correct, TTL."""
import pytest
import uuid
from decimal import Decimal


@pytest.mark.asyncio
async def test_reserve_decreases_available_increases_reserved(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Test", slug="test-s3", sku=f"S3-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("10.000"), created_by=owner.id,
    )
    await db_session.commit()

    reservation = await InventoryService.reserve(
        db_session, inventory_id=item.id, qty=Decimal("3.000"), order_id=None,
    )
    await db_session.commit()

    # Reload
    from app.modules.inventory.models import InventoryItem
    updated = await db_session.get(InventoryItem, item.id)
    assert updated.available_qty == Decimal("7.000")
    assert updated.reserved_qty == Decimal("3.000")
    assert updated.sold_qty == Decimal("0.000")


@pytest.mark.asyncio
async def test_sell_does_not_change_available(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService
    from app.modules.inventory.models import InventoryItem

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Test", slug="test-s3s", sku=f"S3S-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("10.000"), created_by=owner.id,
    )
    await db_session.commit()

    res = await InventoryService.reserve(
        db_session, inventory_id=item.id, qty=Decimal("3.000"), order_id=None,
    )
    await db_session.commit()

    before_sell = item.available_qty
    await InventoryService.sell(db_session, reservation_id=res.id)
    await db_session.commit()

    updated = await db_session.get(InventoryItem, item.id)
    assert updated.available_qty == before_sell, (
        f"INV-001 VIOLATION: sell changed available_qty from {before_sell} to {updated.available_qty}"
    )
    assert updated.reserved_qty == Decimal("0.000")
    assert updated.sold_qty == Decimal("3.000")


@pytest.mark.asyncio
async def test_release_returns_to_available(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService
    from app.modules.inventory.models import InventoryItem

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Test", slug="test-s3r", sku=f"S3R-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("10.000"), created_by=owner.id,
    )
    await db_session.commit()

    res = await InventoryService.reserve(
        db_session, inventory_id=item.id, qty=Decimal("3.000"), order_id=None,
    )
    await db_session.commit()

    await InventoryService.release(db_session, reservation_id=res.id)
    await db_session.commit()

    updated = await db_session.get(InventoryItem, item.id)
    assert updated.available_qty == Decimal("10.000")
    assert updated.reserved_qty == Decimal("0.000")


@pytest.mark.asyncio
async def test_correct_updates_available(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService
    from app.modules.inventory.models import InventoryItem, InventoryMovement

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Test", slug="test-s3c", sku=f"S3C-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("10.000"), created_by=owner.id,
    )
    await db_session.commit()

    await InventoryService.correct(
        db_session, inventory_id=item.id, new_qty=Decimal("15.000"),
        note="Inventory count", created_by=owner.id,
    )
    await db_session.commit()

    updated = await db_session.get(InventoryItem, item.id)
    assert updated.available_qty == Decimal("15.000")

    # Verify movement was written
    movements = await InventoryService.list_movements(db_session, inventory_id=item.id)
    correction_movements = [m for m in movements if m.type == "correction"]
    assert len(correction_movements) >= 1
    assert correction_movements[-1].qty == Decimal("5.000")


@pytest.mark.asyncio
async def test_sell_on_nonexistent_raises(db_session, shop_and_owner):
    from app.modules.inventory.service import InventoryService
    import uuid as _uuid

    with pytest.raises(Exception):
        await InventoryService.sell(db_session, reservation_id=_uuid.uuid4())


@pytest.mark.asyncio
async def test_reserve_insufficient_stock_raises(db_session, shop_and_owner):
    from app.modules.catalog.service import CatalogService
    from app.modules.inventory.service import InventoryService, InsufficientStockError

    shop, owner = shop_and_owner
    product = await CatalogService.create_product(
        db_session, shop_id=shop.id, name="Test", slug="test-s3ins", sku=f"S3INS-{uuid.uuid4().hex[:8]}"
    )
    await db_session.flush()

    item = await InventoryService.initialize(
        db_session, shop_id=shop.id, product_id=product.id,
        initial_qty=Decimal("1.000"), created_by=owner.id,
    )
    await db_session.commit()

    with pytest.raises(InsufficientStockError):
        await InventoryService.reserve(db_session, inventory_id=item.id, qty=Decimal("5.000"))
