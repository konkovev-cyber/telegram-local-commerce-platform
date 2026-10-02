import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_008_orders_and_payments_have_idempotency_key(db_session):
    for table in ("orders", "payments"):
        result = await db_session.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = :t AND column_name = 'idempotency_key'"),
            {"t": table},
        )
        assert result.fetchone() is not None, (
            f"INV-008 VIOLATION: Table '{table}' missing idempotency_key column."
        )
