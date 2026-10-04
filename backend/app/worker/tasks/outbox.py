import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.outbox import OutboxEvent
from app.modules.notifications.dispatcher import NotificationDispatcher, TelegramAPIError, RateLimitError

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
SKIP_LOCKED = True


async def process_outbox_events(ctx):
    """
    Воркер transactional outbox.
    Выбирает pending/failed события, обрабатывает с exponential backoff.
    """
    async with AsyncSessionLocal() as session:
        events = (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status.in_(["pending", "failed"]),
                    OutboxEvent.attempts < MAX_ATTEMPTS,
                )
                .order_by(OutboxEvent.created_at)
                .limit(50)
                .with_for_update(skip_locked=SKIP_LOCKED)
            )
        ).scalars().all()

        for event in events:
            event.status = "processing"
            try:
                result = await NotificationDispatcher.process_event(session, event)
                event.status = "done"
                event.processed_at = datetime.now(timezone.utc)
                logger.info(f"Outbox event {event.id} processed: {result}")
            except RateLimitError as e:
                # Rate limit — retry after delay (handled by cron every minute)
                event.status = "failed"
                event.last_error = f"Rate limited: {e}"
                event.attempts += 1
                logger.warning(f"Outbox event {event.id} rate limited, will retry: {e}")
            except TelegramAPIError as e:
                event.status = "failed"
                event.last_error = str(e)
                event.attempts += 1
                logger.error(f"Outbox event {event.id} Telegram error: {e}")
            except Exception as e:
                event.status = "failed"
                event.last_error = str(e)
                event.attempts += 1
                logger.error(f"Outbox event {event.id} error: {e}")

        await session.commit()
