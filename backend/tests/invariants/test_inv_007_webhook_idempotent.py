import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_inv_007_webhook_unique_constraint_exists(db_session):
    result = await db_session.execute(
        text("""
            SELECT conname FROM pg_constraint
            WHERE conname = 'uq_webhook_provider_event_id'
        """)
    )
    assert result.fetchone() is not None, (
        "INV-007 VIOLATION: Unique constraint uq_webhook_provider_event_id missing on webhook_events."
    )
