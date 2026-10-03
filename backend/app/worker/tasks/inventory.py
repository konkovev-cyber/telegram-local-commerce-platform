import asyncio
import logging
from datetime import datetime, timezone

from app.core.db import AsyncSessionLocal
from app.modules.inventory.service import InventoryService

logger = logging.getLogger(__name__)


async def cleanup_expired_reservations_task(ctx: dict) -> int:
    """ARQ/cron task: release expired reservations every 5 minutes. INV-003 compliant."""
    logger.info("Starting expired reservation cleanup")
    session = AsyncSessionLocal()
    try:
        count = await InventoryService.release_expired(session)
        await session.commit()
        logger.info(f"Released {count} expired reservations")
        return count
    except Exception as e:
        logger.error(f"Failed to release expired reservations: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()
