from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
import uuid


class ShopCreateRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=60, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    currency: str = Field(default="RUB", min_length=3, max_length=3)


class ShopResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    currency: str
    owner_id: str
    plan: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ShopMemberAddRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the user to add")
    shop_role: str = Field(default="operator", pattern=r"^(owner|admin|operator)$")


class ShopMemberResponse(BaseModel):
    shop_id: str
    user_id: str
    shop_role: str

    model_config = ConfigDict(from_attributes=True)


class ShopBotSetRequest(BaseModel):
    bot_username: str = Field(..., min_length=3, max_length=100)
    bot_token: str = Field(..., min_length=30, description="Raw bot token from BotFather")
    mode: str = Field(default="shared", pattern=r"^(shared|dedicated)$")


class ShopBotResponse(BaseModel):
    """INV-009: bot_token/encrypted_token NEVER returned."""
    id: str
    shop_id: str
    bot_username: str
    mode: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ShopListResponse(BaseModel):
    shops: List[ShopResponse]
    total: int
