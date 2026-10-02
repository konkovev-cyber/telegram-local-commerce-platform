import uuid
from typing import Tuple
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.jwt import decode_access_token
from app.modules.auth.models import User
from app.modules.auth.service import UserService
from app.modules.shops.models import Shop, ShopMember
from app.modules.shops.service import ShopMemberService

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    try:
        payload = decode_access_token(auth.credentials)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_shop_context(
    x_shop_id: str = Header(..., alias="X-Shop-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Shop, ShopMember]:
    """
    INV-012: фильтрует по shop_id из заголовка X-Shop-Id и валидирует membership.
    """
    try:
        shop_uuid = uuid.UUID(x_shop_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Shop-Id UUID")

    shop, member = await ShopMemberService.get_shop_and_member(
        db, shop_id=shop_uuid, user_id=current_user.id
    )
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this shop")

    return shop, member


def require_shop_role(*roles: str):
    async def dep(
        shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context)
    ) -> Tuple[Shop, ShopMember]:
        _, member = shop_context
        if member.shop_role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role. Required: {roles}, current: {member.shop_role}",
            )
        return shop_context

    return dep
