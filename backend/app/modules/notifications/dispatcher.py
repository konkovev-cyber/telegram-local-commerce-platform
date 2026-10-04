import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import OutboxEvent
from app.modules.shops.models import ShopBot
from app.modules.shops.crypto import decrypt_bot_token
from app.modules.auth.models import CustomerIdentity, Customer, User
from app.modules.waves.models import Wave

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Simple Telegram Bot API client (no external deps in MVP)."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        url = f"{self.BASE_URL}/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                })
                data = resp.json()
                if not data.get("ok"):
                    error_code = data.get("error_code", 0)
                    desc = data.get("description", "")
                    if error_code == 403:
                        logger.warning(f"Telegram 403: user blocked bot. chat_id={chat_id}, desc={desc}")
                        return False
                    if error_code == 429:
                        retry_after = data.get("parameters", {}).get("retry_after", 5)
                        logger.warning(f"Telegram 429: rate limited. retry_after={retry_after}")
                        raise RateLimitError(f"Retry after {retry_after}s")
                    raise TelegramAPIError(f"Telegram error {error_code}: {desc}")
                return True
        except httpx.TimeoutException:
            raise TelegramAPIError("Telegram API timeout")
        except httpx.HTTPError as e:
            raise TelegramAPIError(f"HTTP error: {e}")


class TelegramAPIError(Exception):
    pass


class RateLimitError(TelegramAPIError):
    pass


class NotificationDispatcher:
    """Dispatches outbox events to Telegram based on event_type."""

    # Notification templates
    TEMPLATES = {
        "order.created": {
            "seller": "🛒 <b>Новый заказ #{number}</b>\n\n💰 {total} {currency}",
            "customer": "✅ <b>Заказ #{number} принят!</b>\n\n💰 Сумма: <b>{total} {currency}</b>\n📅 Выдача: {delivery_date}\n📍 {address}",
        },
        "wave.closed": {
            "customer": "🔒 <b>Приём заказов на волну завершён!</b>\n\nЖдём вас на выдаче 🎉",
        },
        "fulfillment.out_for_delivery": {
            "customer": "🚗 <b>Едем к вам!</b>\n\nБудем на точке в <i>{time_slot}</i>. QR-код для получения — в приложении.",
        },
        "fulfillment.arrived": {
            "customer": "📍 <b>Мы на месте!</b>\n\nПокажите QR-код продавцу для получения заказа.",
        },
        "fulfillment.delivered": {
            "customer": "🎉 <b>Заказ #{number} получен!</b>\n\nСпасибо за покупку! 💐",
        },
        "payment.completed": {
            "customer": "💳 <b>Оплата прошла успешно!</b>\n\nСумма: <b>{amount} {currency}</b>\nЗаказ #{order_number}",
        },
        "order.cancelled": {
            "seller": "❌ <b>Заказ #{number} отменён</b>\n\nПричина: {reason}",
            "customer": "❌ <b>Заказ #{number} отменён</b>\n\n{reason}",
        },
    }

    @staticmethod
    async def process_event(session: AsyncSession, event: OutboxEvent) -> str:
        """Process a single outbox event and return result description."""
        payload = event.payload
        event_type = event.event_type
        shop_id = event.shop_id

        # Check event type first (skip unknown types without DB access)
        if event_type not in NotificationDispatcher.TEMPLATES and event_type not in {
            "wave.closed", "fulfillment.out_for_delivery", "fulfillment.arrived",
            "fulfillment.delivered", "payment.completed", "order.cancelled"
        }:
            return "skipped_unknown_event"

        # Get shop bot token
        bot_token = await NotificationDispatcher._get_bot_token(session, shop_id)
        if not bot_token:
            raise TelegramAPIError("No bot token configured for shop")

        client = TelegramBotClient(bot_token)

        # Dispatch based on event type
        if event_type == "order.created":
            await NotificationDispatcher._dispatch_order_created(session, client, payload)
        elif event_type == "wave.closed":
            await NotificationDispatcher._dispatch_wave_closed(session, client, payload)
        elif event_type == "fulfillment.out_for_delivery":
            await NotificationDispatcher._dispatch_fulfillment(session, client, payload, "out_for_delivery")
        elif event_type == "fulfillment.arrived":
            await NotificationDispatcher._dispatch_fulfillment(session, client, payload, "arrived")
        elif event_type == "fulfillment.delivered":
            await NotificationDispatcher._dispatch_fulfillment(session, client, payload, "delivered")
        elif event_type == "payment.completed":
            await NotificationDispatcher._dispatch_payment_completed(session, client, payload)
        elif event_type == "order.cancelled":
            await NotificationDispatcher._dispatch_order_cancelled(session, client, payload)
        else:
            logger.info(f"Unknown event type: {event_type}")
            return "skipped_unknown_event"

        return "sent"

    @staticmethod
    async def _get_bot_token(session: AsyncSession, shop_id) -> Optional[str]:
        """Get decrypted bot token for shop, fallback to platform bot."""
        stmt = select(ShopBot).where(ShopBot.shop_id == shop_id, ShopBot.is_active == True)
        res = await session.execute(stmt)
        bot = res.scalar_one_or_none()
        if bot:
            return decrypt_bot_token(bot.encrypted_token)

        # Fallback to platform bot
        from app.core.config import settings
        return settings.platform_bot_token

    @staticmethod
    async def _get_customer_chat_id(session: AsyncSession, customer_id) -> Optional[int]:
        """Get Telegram chat ID for a customer."""
        if not customer_id:
            return None
        # Try customer identities first
        stmt = select(CustomerIdentity).where(
            CustomerIdentity.customer_id == customer_id,
            CustomerIdentity.provider == "telegram",
        )
        res = await session.execute(stmt)
        ident = res.scalar_one_or_none()
        if ident:
            try:
                return int(ident.external_id)
            except (ValueError, TypeError):
                pass

        # Fallback to user telegram_id
        from app.modules.auth.models import User as UserModel
        stmt = select(UserModel.telegram_id).where(UserModel.id == customer_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def _get_seller_chats(session: AsyncSession, shop_id) -> list:
        """Get Telegram chat IDs for shop members (sellers)."""
        from app.modules.shops.models import ShopMember
        from app.modules.auth.models import User as UserModel

        stmt = select(ShopMember.user_id).where(ShopMember.shop_id == shop_id)
        res = await session.execute(stmt)
        user_ids = [r[0] for r in res.fetchall()]

        chats = []
        for uid in user_ids:
            stmt = select(UserModel.telegram_id).where(UserModel.id == uid)
            res = await session.execute(stmt)
            tid = res.scalar_one_or_none()
            if tid:
                chats.append(tid)
        return chats

    @staticmethod
    async def _get_wave_info(session: AsyncSession, wave_id) -> Dict[str, Any]:
        """Get wave delivery info for templates."""
        stmt = select(Wave).where(Wave.id == wave_id)
        res = await session.execute(stmt)
        wave = res.scalar_one_or_none()
        if not wave:
            return {}
        return {
            "delivery_date": wave.delivery_date.isoformat() if wave.delivery_date else "",
            "delivery_from": wave.delivery_from.isoformat() if wave.delivery_from else "",
            "delivery_to": wave.delivery_to.isoformat() if wave.delivery_to else "",
        }

    @staticmethod
    async def _dispatch_order_created(session, client, payload):
        order_id = payload.get("order_id")
        number = payload.get("number", "?")
        total = payload.get("total", "0")
        currency = payload.get("currency", "RUB")
        wave_id = payload.get("wave_id")

        from app.modules.orders.models import Order
        stmt = select(Order).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            return

        wave_info = await NotificationDispatcher._get_wave_info(session, wave_id) if wave_id else {}

        # Notify seller(s)
        seller_chats = await NotificationDispatcher._get_seller_chats(session, order.shop_id)
        for chat in seller_chats:
            msg = NotificationDispatcher.TEMPLATES["order.created"]["seller"].format(
                number=number, total=total, currency=currency
            )
            await client.send_message(chat, msg)

        # Notify customer
        customer_chat = await NotificationDispatcher._get_customer_chat_id(session, order.customer_id)
        if customer_chat:
            addr = "Точка выдачи"
            if order.pickup_point_id:
                from app.modules.geo.models import PickupPoint
                p_stmt = select(PickupPoint).where(PickupPoint.id == order.pickup_point_id)
                p_res = await session.execute(p_stmt)
                pp = p_res.scalar_one_or_none()
                if pp:
                    addr = pp.address or pp.name or "Точка выдачи"
            msg = NotificationDispatcher.TEMPLATES["order.created"]["customer"].format(
                number=number, total=total, currency=currency,
                delivery_date=wave_info.get("delivery_date", ""),
                address=addr,
            )
            await client.send_message(customer_chat, msg)

    @staticmethod
    async def _dispatch_wave_closed(session, client, payload):
        wave_id = payload.get("wave_id")
        if not wave_id:
            return

        from app.modules.orders.models import Order
        stmt = select(Order.customer_id.distinct()).where(Order.wave_id == wave_id)
        res = await session.execute(stmt)
        customer_ids = [r[0] for r in res.fetchall() if r[0]]

        wave_info = await NotificationDispatcher._get_wave_info(session, wave_id)

        for cid in customer_ids:
            chat = await NotificationDispatcher._get_customer_chat_id(session, cid)
            if chat:
                msg = NotificationDispatcher.TEMPLATES["wave.closed"]["customer"]
                await client.send_message(chat, msg)

    @staticmethod
    async def _dispatch_fulfillment(session, client, payload, event_name):
        order_id = payload.get("order_id")
        from app.modules.orders.models import Order
        stmt = select(Order).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            return

        customer_chat = await NotificationDispatcher._get_customer_chat_id(session, order.customer_id)
        if not customer_chat:
            return

        template_key = f"fulfillment.{event_name}"
        template = NotificationDispatcher.TEMPLATES.get(template_key, {})
        if not template:
            return

        time_slot = ""
        if order.time_slot_id:
            from app.modules.waves.models import WaveTimeSlot
            ts_stmt = select(WaveTimeSlot).where(WaveTimeSlot.id == order.time_slot_id)
            ts_res = await session.execute(ts_stmt)
            ts = ts_res.scalar_one_or_none()
            if ts:
                time_slot = f"{ts.from_time.isoformat()}–{ts.to_time.isoformat()}"

        msg = template["customer"].format(
            number=order.number, time_slot=time_slot
        )
        await client.send_message(customer_chat, msg)

    @staticmethod
    async def _dispatch_payment_completed(session, client, payload):
        payment_id = payload.get("payment_id")
        order_id = payload.get("order_id")

        from app.modules.payments.models import Payment
        stmt = select(Payment).where(Payment.id == payment_id)
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()
        if not payment:
            return

        # Get order for customer_id
        from app.modules.orders.models import Order
        o_stmt = select(Order).where(Order.id == order_id)
        o_res = await session.execute(o_stmt)
        order = o_res.scalar_one_or_none()

        customer_chat = await NotificationDispatcher._get_customer_chat_id(session, order.customer_id) if order else None
        if not customer_chat:
            return

        msg = NotificationDispatcher.TEMPLATES["payment.completed"]["customer"].format(
            amount=payment.amount, currency=payment.currency,
            order_number=order.number if order else "?",
        )
        await client.send_message(customer_chat, msg)

    @staticmethod
    async def _dispatch_order_cancelled(session, client, payload):
        order_id = payload.get("order_id")
        reason = payload.get("reason", "")

        from app.modules.orders.models import Order
        stmt = select(Order).where(Order.id == order_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            return

        # Notify seller
        seller_chats = await NotificationDispatcher._get_seller_chats(session, order.shop_id)
        msg = NotificationDispatcher.TEMPLATES["order.cancelled"]["seller"].format(
            number=order.number, reason=reason,
        )
        for chat in seller_chats:
            await client.send_message(chat, msg)

        # Notify customer
        customer_chat = await NotificationDispatcher._get_customer_chat_id(session, order.customer_id)
        if customer_chat:
            msg = NotificationDispatcher.TEMPLATES["order.cancelled"]["customer"].format(
                number=order.number, reason=reason,
            )
            await client.send_message(customer_chat, msg)
