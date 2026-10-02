from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., description="Raw initData string from Telegram Mini App")


class TelegramAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_new_user: bool = False


class UserResponse(BaseModel):
    id: str
    telegram_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    platform_role: str

    model_config = ConfigDict(from_attributes=True)
