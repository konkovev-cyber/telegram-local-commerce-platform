import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.config import settings
from app.modules.auth.schemas import TelegramAuthRequest, TelegramAuthResponse, UserResponse
from app.modules.auth.telegram import validate_init_data, TelegramInitDataError
from app.modules.auth.service import UserService
from app.modules.auth.jwt import create_access_token
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/telegram", response_model=TelegramAuthResponse)
async def telegram_login(
    body: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Telegram Mini App login.
    КРИТИЧНО: validate initData, НЕ initDataUnsafe.
    """
    try:
        tg_user = validate_init_data(body.init_data, settings.platform_bot_token)
    except TelegramInitDataError as e:
        logger.warning(f"Telegram auth failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Telegram authentication failed: {e}",
        )

    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram user ID in initData",
        )

    user, is_new = await UserService.get_or_create_from_telegram(
        db,
        telegram_id=telegram_id,
        first_name=tg_user.get("first_name"),
        last_name=tg_user.get("last_name"),
        username=tg_user.get("username"),
        photo_url=tg_user.get("photo_url"),
    )
    await db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})

    return TelegramAuthResponse(
        access_token=access_token,
        user_id=str(user.id),
        is_new_user=is_new,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user profile."""
    return UserResponse(
        id=str(current_user.id),
        telegram_id=current_user.telegram_id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        username=current_user.username,
        photo_url=current_user.photo_url,
        platform_role=current_user.platform_role,
    )
