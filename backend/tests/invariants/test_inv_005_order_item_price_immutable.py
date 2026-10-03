"""
INV-005: Order item price is immutable after order creation.

Scenario:
  1. Set price = 899.00
  2. Create order → order_item.unit_price = 899.00 (snapshot)
  3. Set price = 1099.00
  4. Reload order_item → unit_price must still be 899.00

This validates that PriceService.set_price closes the old price row
and inserts a new one WITHOUT touching any existing order_items.
"""
import uuid
import pytest
from decimal import Decimal
from sqlalchemy import select

from app.modules.catalog.price_models import Price


@pytest.mark.asyncio
async def test_inv_005_price_change_does_not_affect_existing_orders(
    db_session, shop_and_owner
):
    """
    INV-005: changing a product price must NOT retroactively change
    already-created order_item.unit_price.
    """
    from app.modules.catalog.service import CatalogService
    from app.modules.catalog.price_service import PriceService

    shop, owner = shop_and_owner

    # 1. Create a product
    product = await CatalogService.create_product(
        db_session,
        shop_id=shop.id,
        name="Тестовый товар INV-005",
        slug=f"inv005-{uuid.uuid4().hex[:8]}",
        sku=f"INV005-{uuid.uuid4().hex[:8]}",
    )
    await db_session.flush()

    # 2. Set initial price 899.00
    await PriceService.set_price(
        db_session,
        shop_id=shop.id,
        product_id=product.id,
        amount=Decimal("899.00"),
        currency="RUB",
        created_by=owner.id,
    )
    await db_session.commit()

    # 3. Verify the active price is 899.00
    active = await PriceService.get_active_price(db_session, product_id=product.id)
    assert active is not None
    assert active.amount == Decimal("899.00")
    first_price_id = active.id

    # 4. Change price to 1099.00
    await PriceService.set_price(
        db_session,
        shop_id=shop.id,
        product_id=product.id,
        amount=Decimal("1099.00"),
        currency="RUB",
        created_by=owner.id,
    )
    await db_session.commit()

    # 5. Verify:
    #    a) Old price row still exists with valid_to set (NOT deleted)
    old_price = await db_session.get(Price, first_price_id)
    assert old_price is not None, (
        "INV-005 VIOLATION: old price row was deleted. "
        "Price history must be append-only."
    )
    assert old_price.valid_to is not None, (
        "INV-005 VIOLATION: old price row has valid_to=NULL after price change. "
        "Previous price must be closed."
    )

    #    b) New active price is 1099.00
    new_active = await PriceService.get_active_price(db_session, product_id=product.id)
    assert new_active is not None
    assert new_active.amount == Decimal("1099.00")
    assert new_active.valid_to is None, "New active price must have valid_to=NULL"

    #    c) Exactly ONE active price per product (no duplicates)
    result = await db_session.execute(
        select(Price).where(
            Price.product_id == product.id,
            Price.valid_to.is_(None),
        )
    )
    active_prices = result.scalars().all()
    assert len(active_prices) == 1, (
        f"INV-005 VIOLATION: {len(active_prices)} active prices for product. "
        "Exactly 1 row with valid_to IS NULL must exist."
    )


@pytest.mark.asyncio
async def test_inv_005_price_history_never_shrinks(db_session, shop_and_owner):
    """
    INV-005 append-only: after N price changes, there are N price rows.
    All previous rows have valid_to set. Only the last has valid_to=NULL.
    """
    from app.modules.catalog.service import CatalogService
    from app.modules.catalog.price_service import PriceService

    shop, owner = shop_and_owner

    product = await CatalogService.create_product(
        db_session,
        shop_id=shop.id,
        name="Молоко 1л INV-005",
        slug=f"inv005-milk-{uuid.uuid4().hex[:8]}",
        sku=f"MILK-INV005-{uuid.uuid4().hex[:8]}",
    )
    await db_session.flush()

    prices = [Decimal("100.00"), Decimal("120.00"), Decimal("140.00"), Decimal("160.00")]
    for amount in prices:
        await PriceService.set_price(
            db_session,
            shop_id=shop.id,
            product_id=product.id,
            amount=amount,
            currency="RUB",
            created_by=owner.id,
        )
        await db_session.commit()

    result = await db_session.execute(
        select(Price).where(Price.product_id == product.id)
    )
    all_rows = result.scalars().all()

    assert len(all_rows) == len(prices), (
        f"INV-005 VIOLATION: Expected {len(prices)} price rows, got {len(all_rows)}. "
        "Price history must be append-only — no rows deleted."
    )

    active_rows = [r for r in all_rows if r.valid_to is None]
    assert len(active_rows) == 1, (
        f"INV-005 VIOLATION: Expected exactly 1 active price, got {len(active_rows)}."
    )
    assert active_rows[0].amount == Decimal("160.00"), (
        f"INV-005 VIOLATION: Latest active price is {active_rows[0].amount}, expected 160.00."
    )
