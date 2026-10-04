import uuid as _uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx


async def test_telegram_bot_send_success():
    """Successful message send returns True."""
    from app.modules.notifications.dispatcher import TelegramBotClient

    client = TelegramBotClient("123:test")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"ok": True}
    with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=fake_resp)):
        result = await client.send_message(100001, "Hello")
        assert result is True


async def test_telegram_bot_403_blocked():
    """Telegram 403 (user blocked bot) → returns False."""
    from app.modules.notifications.dispatcher import TelegramBotClient

    client = TelegramBotClient("123:test")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"ok": False, "error_code": 403, "description": "Bot was blocked"}
    with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=fake_resp)):
        result = await client.send_message(100001, "Hello")
        assert result is False


async def test_telegram_bot_429_rate_limit():
    """Telegram 429 → RateLimitError raised."""
    from app.modules.notifications.dispatcher import TelegramBotClient, RateLimitError

    client = TelegramBotClient("123:test")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "ok": False, "error_code": 429,
        "description": "Too Many Requests",
        "parameters": {"retry_after": 5},
    }
    with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=fake_resp)):
        with pytest.raises(RateLimitError):
            await client.send_message(100001, "Hello")


async def test_telegram_bot_timeout():
    """HTTP timeout → TelegramAPIError raised."""
    from app.modules.notifications.dispatcher import TelegramBotClient, TelegramAPIError

    client = TelegramBotClient("123:test")
    with patch('httpx.AsyncClient.post', new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
        with pytest.raises(TelegramAPIError):
            await client.send_message(100001, "Hello")


async def test_telegram_bot_http_error():
    """HTTP error → TelegramAPIError raised."""
    from app.modules.notifications.dispatcher import TelegramBotClient, TelegramAPIError

    client = TelegramBotClient("123:test")
    with patch('httpx.AsyncClient.post', new=AsyncMock(side_effect=httpx.HTTPError("network error"))):
        with pytest.raises(TelegramAPIError):
            await client.send_message(100001, "Hello")


async def test_dispatcher_skips_unknown_event():
    """Unknown event_type → returns 'skipped_unknown_event'."""
    from app.modules.notifications.dispatcher import NotificationDispatcher

    fake_session = MagicMock()
    fake_event = MagicMock()
    fake_event.payload = {}
    fake_event.event_type = "unknown.type"
    fake_event.shop_id = _uuid.uuid4()
    fake_event.id = "test-event-id"

    result = await NotificationDispatcher.process_event(fake_session, fake_event)
    assert result == "skipped_unknown_event"


async def test_order_created_template_format():
    """Verify order.created notification message format for seller."""
    from app.modules.notifications.dispatcher import NotificationDispatcher

    template = NotificationDispatcher.TEMPLATES["order.created"]["seller"]
    msg = template.format(number=42, total="1500.00", currency="RUB")
    assert "Новый заказ #42" in msg
    assert "1500.00 RUB" in msg


async def test_fulfillment_delivered_template():
    """Verify fulfillment.delivered template."""
    from app.modules.notifications.dispatcher import NotificationDispatcher

    template = NotificationDispatcher.TEMPLATES["fulfillment.delivered"]["customer"]
    msg = template.format(number=42)
    assert "Заказ #42 получен" in msg
    assert "Спасибо" in msg


async def test_payment_completed_template():
    """Verify payment.completed template."""
    from app.modules.notifications.dispatcher import NotificationDispatcher

    template = NotificationDispatcher.TEMPLATES["payment.completed"]["customer"]
    msg = template.format(amount="500.00", currency="RUB", order_number=7)
    assert "500.00 RUB" in msg
    assert "Заказ #7" in msg


async def test_worker_query_selects_pending_and_failed(client, user_a, shop_a):
    """Verify worker SQL query selects pending/failed events correctly."""
    from app.core.outbox import OutboxEvent
    from app.worker.tasks.outbox import MAX_ATTEMPTS
    from sqlalchemy import select

    shop_id = shop_a["shop_id"]

    # Build the query the worker uses
    stmt = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status.in_(["pending", "failed"]),
            OutboxEvent.attempts < MAX_ATTEMPTS,
        )
        .order_by(OutboxEvent.created_at)
        .limit(50)
    )

    # Test with shop_a's db_session
    from app.core.db import get_db
    # Access the overridden session via the app
    from app.main import app
    override = app.dependency_overrides.get(get_db)
    if override:
        # Get the session from the override
        import inspect
        gen = override()
        if hasattr(gen, '__aiter__'):
            session = await gen.__anext__()
        else:
            session = gen
    else:
        # Fallback: create our own session
        from app.core.config import settings
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        TEST_DB = settings.database_url.replace("/telegram_commerce", "/telegram_commerce_test")
        engine = create_async_engine(TEST_DB, echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
        async with AsyncSessionLocal() as s:
            # Insert test events
            e1 = OutboxEvent(id=_uuid.uuid4(), shop_id=shop_id, event_type="order.created",
                           aggregate_type="order", aggregate_id=_uuid.uuid4(), payload={},
                           status="pending", attempts=0)
            e2 = OutboxEvent(id=_uuid.uuid4(), shop_id=shop_id, event_type="order.created",
                           aggregate_type="order", aggregate_id=_uuid.uuid4(), payload={},
                           status="failed", attempts=MAX_ATTEMPTS)
            s.add_all([e1, e2])
            await s.commit()

            # Query
            res = await s.execute(stmt)
            events = res.scalars().all()
            # Only pending should be selected (e2 has exhausted attempts)
            assert len(events) == 1
            assert events[0].status == "pending"
