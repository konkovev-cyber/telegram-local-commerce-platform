import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.models import User
from app.core.security import get_password_hash


class UserService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        platform_role: str = "user",
        telegram_id: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        photo_url: Optional[str] = None,
    ) -> User:
        hashed = get_password_hash(password) if password else None
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed,
            platform_role=platform_role,
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            photo_url=photo_url,
        )
        session.add(user)
        await session.flush()
        return user

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        return await session.get(User, user_id)

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_or_create_from_telegram(
        session: AsyncSession,
        *,
        telegram_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        photo_url: Optional[str] = None,
    ) -> tuple[User, bool]:
        """
        Find user by telegram_id or create new one.
        Returns (user, is_new_user).
        """
        existing = await UserService.get_by_telegram_id(session, telegram_id)
        if existing:
            # Update profile fields from Telegram on each login
            existing.first_name = first_name
            existing.last_name = last_name
            existing.username = username
            if photo_url:
                existing.photo_url = photo_url
            await session.flush()
            return existing, False

        user = await UserService.create(
            session,
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            photo_url=photo_url,
        )
        return user, True
