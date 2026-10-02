import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_010_outbox_table_exists(db_session):
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name = 'outbox_events'")
    )
    assert result.fetchone() is not None, "INV-010 VIOLATION: outbox_events table missing."
