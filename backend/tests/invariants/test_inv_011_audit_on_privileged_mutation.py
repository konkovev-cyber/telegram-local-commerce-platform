import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_011_audit_table_exists_with_required_fields(db_session):
    result = await db_session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_logs'")
    )
    cols = {r[0] for r in result.fetchall()}
    assert "shop_id" in cols, "INV-011 VIOLATION: audit_logs missing shop_id"
    assert "action" in cols, "INV-011 VIOLATION: audit_logs missing action"
    assert "before" in cols, "INV-011 VIOLATION: audit_logs missing before snapshot"
    assert "after" in cols, "INV-011 VIOLATION: audit_logs missing after snapshot"
