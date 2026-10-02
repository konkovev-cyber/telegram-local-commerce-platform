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
