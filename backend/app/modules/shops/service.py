import uuid
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.shops.models import Shop, ShopMember, ShopBot
from app.modules.shops.crypto import encrypt_bot_token


class ShopService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        slug: str,
        name: str,
        owner_id: uuid.UUID,
        currency: str = "RUB",
        description: Optional[str] = None,
    ) -> Shop:
        shop = Shop(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            owner_id=owner_id,
            currency=currency,
            description=description,
        )
        session.add(shop)
        # Добавляем владельца как участника магазина с ролью 'owner'
        member = ShopMember(
            shop_id=shop.id,
            user_id=owner_id,
            shop_role="owner",
        )
        session.add(member)
        await session.flush()
        return shop

    @staticmethod
    async def get_by_id(session: AsyncSession, shop_id: uuid.UUID) -> Optional[Shop]:
        return await session.get(Shop, shop_id)

    @staticmethod
    async def get_by_slug(session: AsyncSession, slug: str) -> Optional[Shop]:
        stmt = select(Shop).where(Shop.slug == slug)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()


class ShopMemberService:
    @staticmethod
    async def get_shop_and_member(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[Optional[Shop], Optional[ShopMember]]:
        shop = await session.get(Shop, shop_id)
        if not shop:
            return None, None
        stmt = select(ShopMember).where(
            ShopMember.shop_id == shop_id,
            ShopMember.user_id == user_id,
        )
        res = await session.execute(stmt)
        member = res.scalar_one_or_none()
        return shop, member


class ShopBotService:
    @staticmethod
    def encrypt_token(raw_token: str) -> str:
        return encrypt_bot_token(raw_token)

    @staticmethod
    async def set_bot(
        session: AsyncSession,
        *,
        shop_id: uuid.UUID,
        bot_username: str,
        raw_token: str,
        mode: str = "shared",
    ) -> ShopBot:
        encrypted = encrypt_bot_token(raw_token)
        bot = ShopBot(
            id=uuid.uuid4(),
            shop_id=shop_id,
            bot_username=bot_username,
            encrypted_token=encrypted,
            mode=mode,
        )
        session.add(bot)
        await session.flush()
        return bot
