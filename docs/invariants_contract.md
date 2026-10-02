# Architecture Invariants Contract
## Telegram Local Commerce Platform — v1

> ### ⚠️ КРИТИЧЕСКОЕ ПРАВИЛО ДЛЯ AI-РАЗРАБОТЧИКА
> **Invariant tests are SPECIFICATION, not implementation tests.**
> 
> If implementation fails an invariant:
>     **FIX IMPLEMENTATION.**
> 
> **СТРОЖАЙШЕ ЗАПРЕЩЕНО:**
> 1. Weaken assertion (ослаблять проверки или допуски)
> 2. Remove assertion (удалять assert'ы)
> 3. Reduce concurrency (уменьшать число параллельных корутин или размер пула)
> 4. Mock away the database behavior (подменять реальную БД моками)
> 5. Skip the test / mark xfail (`@pytest.mark.skip`, `@pytest.mark.xfail`)
> 6. Change expected behavior (менять ожидаемые коды ответа или состояния)
> 
> Тест инварианта может быть изменён ТОЛЬКО если:
> 1. Изменился `architecture_freeze_v1.md`
> 2. Создан и принят соответствующий ADR
> 3. Изменение явно подтверждено архитектором

---

## Структура

```
backend/
└── tests/
    └── invariants/
        ├── conftest.py
        ├── test_inv_001_inventory_no_direct_update.py
        ├── test_inv_002_reservation_backed_by_item.py
        ├── test_inv_003_inventory_ledger_only.py
        ├── test_inv_004_no_oversell.py
        ├── test_inv_005_order_item_price_immutable.py
        ├── test_inv_006_order_status_no_payment_state.py
        ├── test_inv_007_webhook_idempotent.py
        ├── test_inv_008_mutations_idempotent.py
        ├── test_inv_009_bot_token_encrypted.py
        ├── test_inv_010_order_outbox_atomic.py
        ├── test_inv_011_audit_on_privileged_mutation.py
        ├── test_inv_012_tenant_isolation.py
        └── test_inv_013_tenant_context_authenticated_membership.py
```

---

## conftest.py

```python
# tests/invariants/conftest.py
import asyncio
import uuid
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings

TEST_DATABASE_URL = settings.database_url.replace(
    "/telegram_commerce", "/telegram_commerce_test"
)

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session(setup_db) -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def shop_and_owner(db_session):
    from app.modules.shops.service import ShopService
    from app.modules.auth.service import UserService

    owner = await UserService.create(
        db_session,
        email=f"owner_{uuid.uuid4().hex[:8]}@test.com",
        password="testpass123",
        platform_role="user",
    )
    shop = await ShopService.create(
        db_session,
        slug=f"test-shop-{uuid.uuid4().hex[:8]}",
        name="Test Shop",
        owner_id=owner.id,
        currency="RUB",
    )
    await db_session.commit()
    return shop, owner


@pytest_asyncio.fixture()
async def product_with_inventory(db_session, shop_and_owner):
    from app.modules.catalog.service import ProductService
    from app.modules.inventory.service import InventoryService

    shop, owner = shop_and_owner
    product = await ProductService.create(
        db_session,
        shop_id=shop.id,
        name="Фермерская свинина",
        sku="PORK-001",
        stock_tracking=True,
    )
    inventory = await InventoryService.initialize(
        db_session,
        shop_id=shop.id,
        product_id=product.id,
        initial_qty=Decimal("30.000"),
        created_by=owner.id,
    )
    await db_session.commit()
    return product, inventory, shop, owner
```

---

## INV-001: Inventory quantity cannot be changed directly on products

```python
# tests/invariants/test_inv_001_inventory_no_direct_update.py
"""
INV-001
Запрещено изменять количество товара напрямую через UPDATE products.
Единственный способ изменить остаток — через append-only inventory_movements.
available_qty строго детерминирована суммой движений:
available = initial + purchases + corrections - sales - active_reservations + releases + refunds
"""
import pytest
from decimal import Decimal
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


@pytest.mark.asyncio
async def test_inv_001_available_qty_strictly_derived_from_ledger_lifecycle(
    db_session, product_with_inventory
):
    """
    Доказываем, что available_qty НЕ является независимым полем,
    а строго следует балансу движений сквозь полный цикл:
    1. Исходный остаток: +30
    2. Резервирование под заказ 1: -10 (available=20, reserved=10)
    3. Отмена резерва (release): +5 (available=25, reserved=5)
    4. Продажа (sale): резерв 5 списывается в sold (available=25, reserved=0, sold=5)
    5. Корректировка (correction): +2 (available=27)
    6. Возврат (refund): +1 (available=28)
    """
    from app.modules.inventory.service import InventoryService
    from app.modules.inventory.models import InventoryItem

    product, inventory, shop, owner = product_with_inventory
    inv_id = inventory.id

    # 1. Начальный остаток 30
    item = await db_session.get(InventoryItem, inv_id)
    assert item.available_qty == Decimal("30.000")

    # 2. Резервирование 10 кг
    res1 = await InventoryService.reserve(
        db_session, inventory_id=inv_id, qty=Decimal("10.000"), order_id=None
    )
    await db_session.flush()

    # 3. Резервирование 5 кг
    res2 = await InventoryService.reserve(
        db_session, inventory_id=inv_id, qty=Decimal("5.000"), order_id=None
    )
    await db_session.flush()

    # 4. Освобождение резерва res1 (+10)
    await InventoryService.release(db_session, reservation_id=res1.id)
    await db_session.flush()

    # 5. Списание в продажу res2 (5 кг)
    await InventoryService.sell(db_session, reservation_id=res2.id)
    await db_session.flush()

    # 6. Ручная инвентаризация / корректировка (+2)
    await InventoryService.correct(
        db_session, inventory_id=inv_id, new_qty=Decimal("27.000"),
        note="Инвентаризация", created_by=owner.id
    )
    await db_session.flush()

    # Проверяем, что available_qty строго соответствует расчету из ledger
    result = await db_session.execute(
        text("""
            SELECT
                ii.available_qty,
                ii.reserved_qty,
                ii.sold_qty,
                COALESCE(SUM(
                    CASE 
                        WHEN im.type IN ('purchase', 'reservation_release', 'refund') THEN im.qty
                        WHEN im.type IN ('reservation', 'sale') THEN -ABS(im.qty)
                        WHEN im.type = 'correction' THEN im.qty
                        ELSE 0
                    END
                ), 0) AS calculated_available
            FROM inventory_items ii
            JOIN inventory_movements im ON im.inventory_id = ii.id
            WHERE ii.id = :inv_id
            GROUP BY ii.id, ii.available_qty, ii.reserved_qty, ii.sold_qty
        """),
        {"inv_id": str(inv_id)},
    )
    row = result.fetchone()
    assert row.available_qty == Decimal("27.000")
    assert row.reserved_qty == Decimal("0.000")
    assert row.sold_qty == Decimal("5.000")
    assert row.available_qty == row.calculated_available, (
        f"INV-001 VIOLATION: available_qty ({row.available_qty}) != calculated ({row.calculated_available})."
    )

```

---

## INV-002: Every reservation is backed by an inventory item

```python
# tests/invariants/test_inv_002_reservation_backed_by_item.py
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
```

---

## INV-004: Concurrent reservations cannot oversell stock

```python
# tests/invariants/test_inv_004_no_oversell.py
"""
INV-004
30 кг доступно. 5 конкурентных задач по 10 кг.
Ровно 3 проходят, 2 получают InsufficientStockError.
"""
import asyncio
import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_inv_004_concurrent_reservations_no_oversell(setup_db):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings
    from app.modules.inventory.service import InventoryService
    from app.modules.inventory.exceptions import InsufficientStockError
    from app.modules.inventory.models import InventoryItem, InventoryMovement, InventoryReservation
    from sqlalchemy import select, func
    import uuid

    TEST_DB_URL = settings.database_url.replace(
        "/telegram_commerce", "/telegram_commerce_test"
    )
    eng = create_async_engine(TEST_DB_URL, pool_size=10)
    SessionFactory = async_sessionmaker(eng, expire_on_commit=False)

    async with SessionFactory() as session:
        inv = InventoryItem(
            id=uuid.uuid4(), shop_id=uuid.uuid4(), product_id=uuid.uuid4(),
            available_qty=Decimal("30.000"), reserved_qty=Decimal("0.000"), sold_qty=Decimal("0.000"),
        )
        session.add(inv)
        session.add(InventoryMovement(
            shop_id=inv.shop_id, inventory_id=inv.id, type="purchase",
            qty=Decimal("30.000"), before_available=Decimal("0.000"), after_available=Decimal("30.000"),
        ))
        await session.commit()
        inventory_id = inv.id

    success_count = 0
    failure_count = 0
    errors = []

    # 5 конкурентных запросов по 10 кг при общем наличии 30 кг
    async def try_reserve():
        nonlocal success_count, failure_count
        async with SessionFactory() as session:
            try:
                await InventoryService.reserve(
                    session, inventory_id=inventory_id,
                    qty=Decimal("10.000"), order_id=None, ttl_minutes=15,
                )
                await session.commit()
                success_count += 1
            except InsufficientStockError:
                failure_count += 1
            except Exception as e:
                errors.append(str(e))

    await asyncio.gather(*[try_reserve() for _ in range(5)])

    assert not errors, f"INV-004: Unexpected errors during concurrency: {errors}"
    assert success_count == 3, (
        f"INV-004 VIOLATION: Expected exactly 3 successes, got {success_count}."
    )
    assert failure_count == 2, (
        f"INV-004 VIOLATION: Expected exactly 2 failures, got {failure_count}."
    )

    # Проверка инвариантов состояния в БД:
    async with SessionFactory() as session:
        item = (await session.execute(
            select(InventoryItem).where(InventoryItem.id == inventory_id)
        )).scalar_one()

        assert item.available_qty == Decimal("0.000"), (
            f"INV-004 VIOLATION: Expected available_qty=0.000, got {item.available_qty}"
        )
        assert item.reserved_qty == Decimal("30.000"), (
            f"INV-004 VIOLATION: Expected reserved_qty=30.000, got {item.reserved_qty}"
        )

        res_count = (await session.execute(
            select(func.count()).select_from(InventoryReservation).where(
                InventoryReservation.inventory_id == inventory_id,
                InventoryReservation.status == "active"
            )
        )).scalar()
        assert res_count == 3, f"INV-004 VIOLATION: Expected 3 active reservations, got {res_count}"

        # Проверка суммы резервирований в движениях
        res_mov_sum = (await session.execute(
            select(func.sum(InventoryMovement.qty)).where(
                InventoryMovement.inventory_id == inventory_id,
                InventoryMovement.type == "reservation"
            )
        )).scalar()
        assert res_mov_sum == Decimal("-30.000"), (
            f"INV-004 VIOLATION: Expected -30.000 in movements, got {res_mov_sum}"
        )

    await eng.dispose()
```

---

## INV-005: Order item price is immutable after order creation

```python
# tests/invariants/test_inv_005_order_item_price_immutable.py
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.modules.orders.models import OrderItem


@pytest.mark.asyncio
async def test_inv_005_price_change_does_not_affect_existing_orders(
    db_session, product_with_inventory
):
    from app.modules.orders.service import OrderService
    from app.modules.catalog.service import PriceService

    product, inventory, shop, owner = product_with_inventory

    await PriceService.set_price(db_session, product_id=product.id,
        amount=Decimal("899.00"), currency="RUB", created_by=owner.id)
    await db_session.commit()

    order = await OrderService.create(db_session, shop_id=shop.id,
        customer_id=None, items=[{"product_id": product.id, "qty": "1.000"}],
        idempotency_key="inv005-test")
    await db_session.commit()

    await PriceService.set_price(db_session, product_id=product.id,
        amount=Decimal("1099.00"), currency="RUB", created_by=owner.id)
    await db_session.commit()

    result = await db_session.execute(
        select(OrderItem).where(OrderItem.order_id == order.id))
    items = result.scalars().all()

    assert items[0].unit_price == Decimal("899.00"), (
        f"INV-005 VIOLATION: order_item price changed to {items[0].unit_price}. "
        "Order snapshots must be immutable."
    )
```

---

## INV-006: Order status cannot contain payment state

```python
# tests/invariants/test_inv_006_order_status_no_payment_state.py
import pytest
from sqlalchemy import text

PAYMENT_STATES = {"paid", "unpaid", "pending_payment", "cash_on_delivery",
                  "payment_failed", "refunded", "partially_paid"}


@pytest.mark.asyncio
async def test_inv_006_check_constraint_excludes_payment_states(db_session):
    result = await db_session.execute(
        text("""
            SELECT cc.check_clause
            FROM information_schema.check_constraints cc
            JOIN information_schema.constraint_column_usage ccu
                ON cc.constraint_name = ccu.constraint_name
            WHERE ccu.table_name = 'orders' AND ccu.column_name = 'order_status'
        """)
    )
    constraints = result.fetchall()
    assert len(constraints) >= 1, (
        "INV-006 VIOLATION: No CHECK constraint on orders.order_status."
    )
    for row in constraints:
        for state in PAYMENT_STATES:
            assert state not in row.check_clause.lower(), (
                f"INV-006 VIOLATION: Payment state '{state}' in order_status constraint."
            )


@pytest.mark.asyncio
async def test_inv_006_separate_payment_and_fulfillment_tables(db_session):
    for table in ("payments", "fulfillments"):
        result = await db_session.execute(
            text("SELECT table_name FROM information_schema.tables "
                 "WHERE table_name = :t AND table_schema = 'public'"),
            {"t": table},
        )
        assert result.fetchone() is not None, (
            f"INV-006 VIOLATION: Table '{table}' missing. Must be separate from orders."
        )
```

---

## INV-007: Payment webhook processing is idempotent

```python
# tests/invariants/test_inv_007_webhook_idempotent.py
import pytest
from sqlalchemy import select, func
from app.modules.payments.models import WebhookEvent, PaymentTransaction, Payment
from app.core.outbox import OutboxEvent


@pytest.mark.asyncio
async def test_inv_007_duplicate_webhook_produces_single_business_effect(
    client, db_session, product_with_inventory
):
    """
    INV-007
    Дублированный webhook (например, retry от ЮKassa/Telegram) не должен производить
    повторный бизнес-эффект:
    webhook x 2
          ↓
    webhook_events record x 1
          ↓
    payment_transactions x 1
          ↓
    payment state transition x 1 (status=paid)
          ↓
    outbox_events notification x 1
    """
    from app.modules.orders.service import OrderService
    from app.modules.payments.service import PaymentService
    from decimal import Decimal
    import uuid

    product, inventory, shop, owner = product_with_inventory

    # 1. Создаем заказ и платеж
    order = await OrderService.create(
        db_session, shop_id=shop.id, customer_id=None,
        items=[{"product_id": product.id, "qty": "1.000"}],
        idempotency_key=f"inv007-ord-{uuid.uuid4().hex}"
    )
    payment = await PaymentService.create(
        db_session, order_id=order.id, shop_id=shop.id,
        amount=Decimal("899.00"), currency="RUB", method="yookassa"
    )
    await db_session.commit()

    provider_event_id = f"evt_inv007_{uuid.uuid4().hex[:12]}"
    payload = {
        "event": "payment.succeeded",
        "object": {
            "id": f"yoo_{uuid.uuid4().hex[:10]}",
            "status": "succeeded",
            "amount": {"value": "899.00", "currency": "RUB"},
            "metadata": {"payment_id": str(payment.id), "order_id": str(order.id)}
        }
    }
    headers = {"X-Provider-Event-Id": provider_event_id}

    # Отправляем один и тот же webhook дважды
    r1 = await client.post("/api/v1/payments/webhook/yookassa", json=payload, headers=headers)
    r2 = await client.post("/api/v1/payments/webhook/yookassa", json=payload, headers=headers)

    assert r1.status_code in (200, 202)
    assert r2.status_code in (200, 202)

    # 1. Проверяем ровно 1 запись webhook_events
    wh_count = (await db_session.execute(
        select(func.count()).select_from(WebhookEvent).where(
            WebhookEvent.provider_event_id == provider_event_id
        )
    )).scalar()
    assert wh_count == 1, f"INV-007 VIOLATION: Duplicate webhook events in DB: {wh_count}"

    # 2. Проверяем ровно 1 транзакцию списания (payment_transactions)
    tx_count = (await db_session.execute(
        select(func.count()).select_from(PaymentTransaction).where(
            PaymentTransaction.payment_id == payment.id,
            PaymentTransaction.type == "charge"
        )
    )).scalar()
    assert tx_count == 1, f"INV-007 VIOLATION: Expected 1 transaction, got {tx_count}"

    # 3. Проверяем статус платежа
    p = await db_session.get(Payment, payment.id)
    assert p.status == "paid"

    # 4. Проверяем, что событие в outbox для отправки уведомления создано ровно 1 раз
    outbox_count = (await db_session.execute(
        select(func.count()).select_from(OutboxEvent).where(
            OutboxEvent.aggregate_id == payment.id,
            OutboxEvent.event_type == "payment.completed"
        )
    )).scalar()
    assert outbox_count == 1, f"INV-007 VIOLATION: Duplicate notification outbox events: {outbox_count}"
```

---

## INV-008: Externally-triggered mutations support idempotency

```python
# tests/invariants/test_inv_008_mutations_idempotent.py
import pytest
from sqlalchemy import select, func
from app.modules.orders.models import Order


@pytest.mark.asyncio
async def test_inv_008_duplicate_order_returns_same_id(
    client, product_with_inventory
):
    product, inventory, shop, owner = product_with_inventory
    key = "idempotency-inv008-unique"
    payload = {"shop_id": str(shop.id),
               "items": [{"product_id": str(product.id), "qty": "1.000"}]}
    headers = {"Idempotency-Key": key, "X-Shop-Id": str(shop.id)}

    r1 = await client.post("/api/v1/orders", json=payload, headers=headers)
    r2 = await client.post("/api/v1/orders", json=payload, headers=headers)

    assert r1.json()["id"] == r2.json()["id"], (
        "INV-008 VIOLATION: Same Idempotency-Key produced different order IDs."
    )
```

---

## INV-009: Shop bot tokens are never stored plaintext

```python
# tests/invariants/test_inv_009_bot_token_encrypted.py
import re
import pytest
from sqlalchemy import text

TELEGRAM_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")


@pytest.mark.asyncio
async def test_inv_009_no_plaintext_tokens(db_session):
    result = await db_session.execute(
        text("SELECT id, encrypted_token FROM shop_bots"))
    violations = [str(r.id) for r in result.fetchall()
                  if TELEGRAM_TOKEN_RE.match(r.encrypted_token)]
    assert not violations, (
        f"INV-009 VIOLATION: {len(violations)} plaintext bot tokens in DB: {violations}"
    )


def test_inv_009_encrypt_token_is_not_identity():
    from app.modules.shops.service import ShopBotService
    raw = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"
    encrypted = ShopBotService.encrypt_token(raw)
    assert encrypted != raw, "INV-009 VIOLATION: encrypt_token returned plaintext."
    assert not TELEGRAM_TOKEN_RE.match(encrypted), (
        "INV-009 VIOLATION: Encrypted token matches plaintext pattern."
    )
```

---

## INV-010: Order + outbox event are committed atomically

```python
# tests/invariants/test_inv_010_order_outbox_atomic.py
import pytest
from sqlalchemy import select, func
from app.core.outbox import OutboxEvent
from app.modules.orders.models import Order
import uuid


@pytest.mark.asyncio
async def test_inv_010_order_and_outbox_committed_atomically(
    db_session, product_with_inventory
):
    """
    INV-010: при COMMIT создается ровно 1 заказ и ровно 1 событие outbox.
    """
    from app.modules.orders.service import OrderService

    product, inventory, shop, owner = product_with_inventory
    key = f"outbox-inv010-{uuid.uuid4().hex}"

    order = await OrderService.create(
        db_session, shop_id=shop.id, customer_id=None,
        items=[{"product_id": product.id, "qty": "1.000"}],
        idempotency_key=key,
    )
    await db_session.commit()

    order_in_db = await db_session.get(Order, order.id)
    assert order_in_db is not None, "Order must exist after commit"

    outbox_result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == order.id,
            OutboxEvent.event_type == "order.created",
        )
    )
    assert outbox_result.scalar_one_or_none() is not None, (
        "INV-010 VIOLATION: outbox_event missing after successful order commit."
    )


@pytest.mark.asyncio
async def test_inv_010_no_order_and_no_outbox_on_transaction_rollback(
    db_session, product_with_inventory
):
    """
    INV-010: при ROLLBACK ни заказ, ни outbox_event НЕ должны остаться в БД.
    Это доказывает, что outbox пишется В ТОЙ ЖЕ транзакции, а не асинхронно
    отдельным сервисом/воркером до коммита.
    """
    from app.modules.orders.service import OrderService

    product, inventory, shop, owner = product_with_inventory
    key = f"outbox-inv010-rollback-{uuid.uuid4().hex}"

    # Создаем заказ внутри текущей транзакции (без коммита)
    order = await OrderService.create(
        db_session, shop_id=shop.id, customer_id=None,
        items=[{"product_id": product.id, "qty": "1.000"}],
        idempotency_key=key,
    )
    await db_session.flush()
    order_id = order.id

    # Проверяем, что в незакомиченной транзакции сущности уже есть
    assert await db_session.get(Order, order_id) is not None

    # Явный откат транзакции
    await db_session.rollback()

    # После rollback проверяем: ни заказа, ни outbox нет в БД
    order_after = await db_session.get(Order, order_id)
    assert order_after is None, "INV-010 VIOLATION: Order survived rollback"

    outbox_count = (await db_session.execute(
        select(func.count()).select_from(OutboxEvent).where(
            OutboxEvent.aggregate_id == order_id
        )
    )).scalar()
    assert outbox_count == 0, (
        f"INV-010 VIOLATION: {outbox_count} outbox events survived rollback! "
        "Outbox event was committed outside the order transaction."
    )
```

---

## INV-011: Privileged mutations produce audit_log

```python
# tests/invariants/test_inv_011_audit_on_privileged_mutation.py
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.modules.audit.models import AuditLog


@pytest.mark.asyncio
async def test_inv_011_price_change_audited(db_session, product_with_inventory):
    from app.modules.catalog.service import PriceService

    product, inventory, shop, owner = product_with_inventory
    await PriceService.set_price(db_session, product_id=product.id,
        amount=Decimal("1099.00"), currency="RUB", created_by=owner.id)
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "product.price_change",
                               AuditLog.entity_id == product.id))
    log = result.scalar_one_or_none()
    assert log is not None, "INV-011 VIOLATION: No audit_log for product.price_change."
    assert log.before is not None and log.after is not None, (
        "INV-011: audit_log must contain before and after snapshots."
    )


@pytest.mark.asyncio
async def test_inv_011_stock_correction_audited(db_session, product_with_inventory):
    from app.modules.inventory.service import InventoryService

    product, inventory, shop, owner = product_with_inventory
    await InventoryService.correct(db_session, inventory_id=inventory.id,
        new_qty=Decimal("20.000"), note="Test", created_by=owner.id)
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "stock.correction",
                               AuditLog.entity_id == inventory.id))
    assert result.scalar_one_or_none() is not None, (
        "INV-011 VIOLATION: No audit_log for stock.correction."
    )
```

---

## INV-012: Tenant records isolated by shop_id

```python
# tests/invariants/test_inv_012_tenant_isolation.py
import pytest, uuid
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_012_shop_a_cannot_see_shop_b_orders(client, db_session):
    from app.modules.shops.service import ShopService
    from app.modules.auth.service import UserService
    from app.modules.auth.jwt import create_access_token
    from app.modules.orders.models import Order

    owner_a = await UserService.create(db_session,
        email=f"a_{uuid.uuid4().hex[:6]}@test.com", password="pass")
    shop_a = await ShopService.create(db_session, slug=f"sa-{uuid.uuid4().hex[:6]}",
        name="Shop A", owner_id=owner_a.id)
    owner_b = await UserService.create(db_session,
        email=f"b_{uuid.uuid4().hex[:6]}@test.com", password="pass")
    shop_b = await ShopService.create(db_session, slug=f"sb-{uuid.uuid4().hex[:6]}",
        name="Shop B", owner_id=owner_b.id)
    await db_session.commit()

    order_b = Order(shop_id=shop_b.id, customer_id=uuid.uuid4(), number=1,
        order_status="new", currency="RUB", subtotal=100, total=100,
        idempotency_key=f"iso-{uuid.uuid4().hex}")
    db_session.add(order_b)
    await db_session.commit()

    token_a = create_access_token({"sub": str(owner_a.id), "shop_id": str(shop_a.id)})
    
    # 1. Проверка списка: заказ чужого магазина не попадает в выдачу
    resp = await client.get("/api/v1/admin/orders",
        headers={"Authorization": f"Bearer {token_a}", "X-Shop-Id": str(shop_a.id)})
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()["items"]]
    assert str(order_b.id) not in ids, (
        "INV-012 VIOLATION: Shop A can see Shop B orders in list. Tenant isolation broken."
    )

    # 2. Негативный IDOR-тест: прямой запрос чужого заказа по ID обязан возвращать 404 (или 403)
    resp_detail = await client.get(f"/api/v1/admin/orders/{order_b.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Shop-Id": str(shop_a.id)})
    assert resp_detail.status_code in (404, 403), (
        f"INV-012 VIOLATION: Shop A accessed Shop B order directly by ID! HTTP {resp_detail.status_code}"
    )


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
```

---

## INV-013: Tenant context MUST be derived from authenticated identity and verified shop membership

```python
# tests/invariants/test_inv_013_tenant_context_authenticated_membership.py
"""
INV-013
Client-provided shop_id/header MUST NEVER grant tenant access.
A valid user from Shop A cannot access Shop B by changing:
    - X-Shop-Id header
    - URL shop_id
    - query parameter
    - path parameter
    - nested entity UUID (orders/items, products, waves, payments)
"""
```

---

## Запуск

```bash
# Инварианты (< 60 сек)
pytest tests/invariants/ -v --tb=short

# Race-condition тест отдельно (медленный)
pytest tests/invariants/test_inv_004_no_oversell.py -v -s

# CI — обязательно перед merge
pytest tests/invariants/ -v --tb=long --junitxml=invariants-report.xml
```

