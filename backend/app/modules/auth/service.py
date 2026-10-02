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
    ) -> User:
        hashed = get_password_hash(password) if password else None
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed,
            platform_role=platform_role,
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
