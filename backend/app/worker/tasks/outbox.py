import logging
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.outbox import OutboxEvent

logger = logging.getLogger(__name__)


async def process_outbox_events(ctx):
    """
    Воркер transactional outbox с блокировкой skip_locked
    для параллельной безопасной обработки без гонок.
    """
    async with AsyncSessionLocal() as session:
        events = (
            await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .order_by(OutboxEvent.created_at)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        for event in events:
            try:
                # В S0 регистрируем готовность к диспетчеризации
                event.status = "done"
            except Exception as e:
                logger.error(f"Error processing outbox event {event.id}: {e}")
                event.status = "failed"
                event.last_error = str(e)
                event.attempts += 1
        await session.commit()
