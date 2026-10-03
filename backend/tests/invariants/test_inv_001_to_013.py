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


@pytest.mark.asyncio
async def test_inv_002_no_orphaned_reservations(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'inventory_reservations'")
    )
    if result.fetchone() is None:
        pytest.skip("inventory_reservations table not present (S0+ migration scope)")
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


@pytest.mark.asyncio
async def test_inv_003_inventory_ledger_only(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'inventory_movements'")
    )
    if result.fetchone() is None:
        pytest.skip("inventory_movements table not present (S0+ migration scope)")
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventory_movements'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "inventory_id" in cols
    assert "type" in cols
    assert "qty" in cols
    assert "before_available" in cols
    assert "after_available" in cols


@pytest.mark.asyncio
async def test_inv_004_no_oversell(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'inventory_reservations'")
    )
    if result.fetchone() is None:
        pytest.skip("inventory_reservations table not present (S0+ migration scope)")
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventory_reservations'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "inventory_id" in cols
    assert "qty" in cols
    assert "expires_at" in cols
    assert "status" in cols


@pytest.mark.asyncio
async def test_inv_005_order_item_price_immutable(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'order_items'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "product_name" in cols, "INV-005 VIOLATION: order_items missing product_name snapshot"
    assert "unit_price" in cols, "INV-005 VIOLATION: order_items missing unit_price snapshot"


@pytest.mark.asyncio
async def test_inv_006_check_constraint_excludes_payment_states(db_session):
    PAYMENT_STATES = {"paid", "unpaid", "pending_payment", "cash_on_delivery",
                      "payment_failed", "refunded", "partially_paid"}
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
        if result.fetchone() is None:
            pytest.skip(f"Table '{table}' not present — not in S2-A scope")
        cols_result = await db_session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
            {"t": table},
        )
        col_names = {r[0] for r in cols_result.fetchall()}
        assert "id" in col_names, f"INV-006 VIOLATION: Table '{table}' has no id column"


@pytest.mark.asyncio
async def test_inv_007_webhook_idempotent(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'webhook_events'")
    )
    if result.fetchone() is None:
        pytest.skip("webhook_events table not present (S0+ migration scope)")
    result = await db_session.execute(
        text("""
            SELECT conname FROM pg_constraint
            WHERE conname = 'uq_webhook_provider_event_id'
        """)
    )
    assert result.fetchone() is not None, (
        "INV-007 VIOLATION: Unique constraint uq_webhook_provider_event_id missing on webhook_events."
    )


@pytest.mark.asyncio
async def test_inv_008_mutations_idempotent(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name = 'orders' AND column_name = 'idempotency_key'")
    )
    assert result.fetchone() is not None, (
        "INV-008 VIOLATION: Table 'orders' missing idempotency_key column."
    )
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'payments'")
    )
    if result.fetchone() is not None:
        result = await db_session.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = 'payments' AND column_name = 'idempotency_key'")
        )
        assert result.fetchone() is not None, (
            "INV-008 VIOLATION: Table 'payments' missing idempotency_key column."
        )


@pytest.mark.asyncio
async def test_inv_009_no_plaintext_tokens(db_session):
    import re
    TELEGRAM_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")
    result = await db_session.execute(
        text("SELECT id, encrypted_token FROM shop_bots")
    )
    violations = [str(r.id) for r in result.fetchall()
                  if TELEGRAM_TOKEN_RE.match(str(r.encrypted_token))]
    assert not violations, (
        f"INV-009 VIOLATION: {len(violations)} plaintext bot tokens in DB: {violations}"
    )


def test_inv_009_encrypt_token_is_not_identity():
    from app.modules.shops.service import ShopBotService
    raw = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"
    encrypted = ShopBotService.encrypt_token(raw)
    assert encrypted != raw, "INV-009 VIOLATION: encrypt_token returned plaintext."
    import re
    TELEGRAM_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")
    assert not TELEGRAM_TOKEN_RE.match(encrypted), (
        "INV-009 VIOLATION: Encrypted token matches plaintext pattern."
    )


@pytest.mark.asyncio
async def test_inv_010_outbox_atomic(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'outbox_events'")
    )
    if result.fetchone() is None:
        pytest.skip("outbox_events table not present (S0+ migration scope)")
    assert result.fetchone() is not None, "INV-010 VIOLATION: outbox_events table missing."


@pytest.mark.asyncio
async def test_inv_011_audit_on_privileged_mutation(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_logs'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "shop_id" in cols, "INV-011 VIOLATION: audit_logs missing shop_id"
    assert "action" in cols, "INV-011 VIOLATION: audit_logs missing action"
    assert "before" in cols, "INV-011 VIOLATION: audit_logs missing before snapshot"
    assert "after" in cols, "INV-011 VIOLATION: audit_logs missing after snapshot"


@pytest.mark.asyncio
async def test_inv_012_all_tenant_tables_have_shop_id(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    )
    existing_tables = {r[0] for r in result.fetchall()}

    candidate_tables = [
        "categories", "products", "product_variants",
        "orders",
        # "shops" — it IS the tenant root, no shop_id column
        "audit_logs", "shop_members", "units",
        "payment_accounts", "shop_bots",
    ]
    for table in candidate_tables:
        if table not in existing_tables:
            continue
        result = await db_session.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = :t AND column_name = 'shop_id'"),
            {"t": table},
        )
        assert result.fetchone() is not None, (
            f"INV-012 VIOLATION: Table '{table}' missing shop_id column."
        )


@pytest.mark.asyncio
async def test_inv_013_nested_resources_and_mutations_protected(client, db_session):
    """
    INV-013: Tenant Context Authenticated Membership Invariant
    User from Shop A cannot access Shop B resources via X-Shop-Id header spoofing.
    """
    import uuid as _uuid
    from app.modules.auth.jwt import create_access_token
    from app.modules.shops.service import ShopService
    from app.modules.auth.service import UserService

    owner_a = await UserService.create(
        db_session, email=f"a_{_uuid.uuid4().hex[:6]}@test.com", platform_role="user"
    )
    shop_a = await ShopService.create(
        db_session, slug=f"sha-{_uuid.uuid4().hex[:6]}", name="Shop A",
        owner_id=owner_a.id, currency="RUB",
    )
    await db_session.commit()

    owner_b = await UserService.create(
        db_session, email=f"b_{_uuid.uuid4().hex[:6]}@test.com", platform_role="user"
    )
    shop_b = await ShopService.create(
        db_session, slug=f"shb-{_uuid.uuid4().hex[:6]}", name="Shop B",
        owner_id=owner_b.id, currency="USD",
    )
    await db_session.commit()

    token_a = create_access_token({"sub": str(owner_a.id)})
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Shop-Id": str(shop_a.id)}

    token_b = create_access_token({"sub": str(owner_b.id)})
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Shop-Id": str(shop_b.id)}

    prod_b = await client.post("/api/v1/admin/products", headers=headers_b, json={
        "name": "B-Product", "slug": "b-prod", "sku": "B-IDOR-TEST"
    })
    assert prod_b.status_code == 201, f"Failed to create product in shop B: {prod_b.text}"
    prod_b_id = prod_b.json()["id"]

    # User A tries to read Shop B's product → 403
    r_get = await client.get(f"/api/v1/admin/products/{prod_b_id}", headers=headers_a)
    assert r_get.status_code in (403, 404), (
        f"INV-013 VIOLATION: User A read Shop B product! HTTP {r_get.status_code}"
    )

    # User A tries PATCH on shop B's product
    r_patch = await client.patch(
        f"/api/v1/admin/products/{prod_b_id}",
        json={"name": "Hacked"},
        headers=headers_a,
    )
    assert r_patch.status_code in (403, 404), (
        f"INV-013 VIOLATION: User A mutated Shop B product! HTTP {r_patch.status_code}"
    )
