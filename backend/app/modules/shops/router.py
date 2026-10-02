import logging
import uuid
from typing import Tuple, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user, get_shop_context, require_shop_role
from app.modules.auth.models import User
from app.modules.shops.models import Shop, ShopMember, ShopBot
from app.modules.shops.schemas import (
    ShopCreateRequest, ShopResponse, ShopListResponse,
    ShopMemberAddRequest, ShopMemberResponse,
    ShopBotSetRequest, ShopBotResponse,
)
from app.modules.shops.service import ShopService, ShopMemberService, ShopBotService
from app.modules.audit.service import write_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin: Shops"])


# ─── Schema for PATCH ──────────────────────────────────────────

class ShopUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    is_active: Optional[bool] = None


# ─── Shop CRUD (no DELETE in S1) ───────────────────────────────

@router.post("/shops", response_model=ShopResponse, status_code=status.HTTP_201_CREATED)
async def create_shop(
    body: ShopCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new shop.
    NO X-Shop-Id required — this creates a new shop context.
    The authenticated user becomes OWNER atomically:
      shop + owner membership + audit → ONE transaction.
    """
    existing = await ShopService.get_by_slug(db, body.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Shop slug already taken")

    # ShopService.create already creates shop + owner ShopMember atomically
    shop = await ShopService.create(
        db,
        slug=body.slug,
        name=body.name,
        owner_id=current_user.id,
        currency=body.currency,
        description=body.description,
    )

    # INV-011: audit log — same transaction as shop creation
    await write_audit(
        db,
        shop_id=shop.id,
        actor_id=current_user.id,
        action="SHOP_CREATED",
        entity_type="shop",
        entity_id=shop.id,
        after={"slug": shop.slug, "name": shop.name, "currency": shop.currency},
    )
    await db.commit()

    return ShopResponse(
        id=str(shop.id),
        slug=shop.slug,
        name=shop.name,
        description=shop.description,
        logo_url=shop.logo_url,
        currency=shop.currency,
        owner_id=str(shop.owner_id),
        plan=shop.plan,
        is_active=shop.is_active,
    )


@router.get("/shops/my", response_model=ShopListResponse)
async def list_my_shops(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List shops where current user is a member.
    NO X-Shop-Id — returns all shops for this user.
    """
    stmt = (
        select(Shop)
        .join(ShopMember, Shop.id == ShopMember.shop_id)
        .where(ShopMember.user_id == current_user.id)
        .order_by(Shop.created_at.desc())
    )
    result = await db.execute(stmt)
    shops = result.scalars().all()

    return ShopListResponse(
        shops=[
            ShopResponse(
                id=str(s.id),
                slug=s.slug,
                name=s.name,
                description=s.description,
                logo_url=s.logo_url,
                currency=s.currency,
                owner_id=str(s.owner_id),
                plan=s.plan,
                is_active=s.is_active,
            )
            for s in shops
        ],
        total=len(shops),
    )


@router.get("/shops/{shop_id}", response_model=ShopResponse)
async def get_shop(
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
):
    """
    Get shop details.
    X-Shop-Id is a SELECTOR — backend verifies JWT user → shop_members.
    INV-012 + INV-013: membership required.
    """
    shop, _ = shop_context
    return ShopResponse(
        id=str(shop.id),
        slug=shop.slug,
        name=shop.name,
        description=shop.description,
        logo_url=shop.logo_url,
        currency=shop.currency,
        owner_id=str(shop.owner_id),
        plan=shop.plan,
        is_active=shop.is_active,
    )


@router.patch("/shops/{shop_id}", response_model=ShopResponse)
async def update_shop(
    body: ShopUpdateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update shop. Owner or admin only.
    INV-011: mutation + audit in one transaction.
    INV-012 + INV-013: tenant context verified via JWT + membership.
    """
    shop, member = shop_context

    before = {}
    after = {}

    if body.name is not None and body.name != shop.name:
        before["name"] = shop.name
        shop.name = body.name
        after["name"] = body.name

    if body.description is not None and body.description != shop.description:
        before["description"] = shop.description
        shop.description = body.description
        after["description"] = body.description

    if body.currency is not None and body.currency != shop.currency:
        before["currency"] = shop.currency
        shop.currency = body.currency
        after["currency"] = body.currency

    if body.is_active is not None and body.is_active != shop.is_active:
        before["is_active"] = shop.is_active
        shop.is_active = body.is_active
        after["is_active"] = body.is_active

    if not after:
        # Nothing changed
        return ShopResponse(
            id=str(shop.id), slug=shop.slug, name=shop.name,
            description=shop.description, logo_url=shop.logo_url,
            currency=shop.currency, owner_id=str(shop.owner_id),
            plan=shop.plan, is_active=shop.is_active,
        )

    # INV-011: audit in same transaction
    await write_audit(
        db,
        shop_id=shop.id,
        actor_id=member.user_id,
        action="SHOP_UPDATED",
        entity_type="shop",
        entity_id=shop.id,
        before=before,
        after=after,
    )
    await db.commit()

    return ShopResponse(
        id=str(shop.id), slug=shop.slug, name=shop.name,
        description=shop.description, logo_url=shop.logo_url,
        currency=shop.currency, owner_id=str(shop.owner_id),
        plan=shop.plan, is_active=shop.is_active,
    )


# ─── Members ───────────────────────────────────────────────────

@router.post(
    "/shops/{shop_id}/members",
    response_model=ShopMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    shop_id: str,
    body: ShopMemberAddRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a member to the shop. Requires owner or admin role.
    INV-011: membership mutation + audit → one transaction.
    INV-012 + INV-013: tenant context via JWT + membership.
    """
    shop, current_member = shop_context

    try:
        target_user_id = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id UUID")

    # Check target user exists
    from app.modules.auth.service import UserService
    target_user = await UserService.get_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already a member
    existing_stmt = select(ShopMember).where(
        ShopMember.shop_id == shop.id,
        ShopMember.user_id == target_user_id,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this shop")

    member = ShopMember(
        shop_id=shop.id,
        user_id=target_user_id,
        shop_role=body.shop_role,
    )
    db.add(member)

    # INV-011: audit — same transaction
    await write_audit(
        db,
        shop_id=shop.id,
        actor_id=current_member.user_id,
        action="MEMBER_ADDED",
        entity_type="shop_member",
        entity_id=target_user_id,
        after={"user_id": str(target_user_id), "shop_role": body.shop_role},
    )
    await db.commit()

    return ShopMemberResponse(
        shop_id=str(shop.id),
        user_id=str(target_user_id),
        shop_role=body.shop_role,
    )


@router.delete("/shops/{shop_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_user_id: str,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a member from the shop.
    Cannot remove the owner. Owner/admin only.
    """
    shop, current_member = shop_context

    try:
        target_user_id = uuid.UUID(member_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id UUID")

    # Find the member
    stmt = select(ShopMember).where(
        ShopMember.shop_id == shop.id,
        ShopMember.user_id == target_user_id,
    )
    target_member = (await db.execute(stmt)).scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot remove owner
    if target_member.shop_role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove shop owner")

    await db.delete(target_member)

    # INV-011: audit — same transaction
    await write_audit(
        db,
        shop_id=shop.id,
        actor_id=current_member.user_id,
        action="MEMBER_REMOVED",
        entity_type="shop_member",
        entity_id=target_user_id,
        before={"user_id": str(target_user_id), "shop_role": target_member.shop_role},
    )
    await db.commit()


@router.get("/shops/{shop_id}/members", response_model=list[ShopMemberResponse])
async def list_members(
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a shop. Requires membership."""
    shop, _ = shop_context
    stmt = select(ShopMember).where(ShopMember.shop_id == shop.id)
    result = await db.execute(stmt)
    members = result.scalars().all()

    return [
        ShopMemberResponse(
            shop_id=str(m.shop_id),
            user_id=str(m.user_id),
            shop_role=m.shop_role,
        )
        for m in members
    ]


# ─── Bot Token ─────────────────────────────────────────────────

@router.post(
    "/shops/{shop_id}/bot",
    response_model=ShopBotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_shop_bot(
    shop_id: str,
    body: ShopBotSetRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    """
    Set shop bot token. Owner only.
    INV-009: token encrypted via Fernet before DB storage.
    INV-013: tenant context verified via JWT + membership.
    bot_token/encrypted_token NEVER returned in response.
    Plaintext token NEVER appears in audit before/after.
    """
    shop, current_member = shop_context

    # Check if bot already exists
    existing_stmt = select(ShopBot).where(ShopBot.shop_id == shop.id)
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Bot already configured for this shop. Delete first.",
        )

    bot = await ShopBotService.set_bot(
        db,
        shop_id=shop.id,
        bot_username=body.bot_username,
        raw_token=body.bot_token,
        mode=body.mode,
    )

    # INV-011: audit — NEVER log the raw token
    await write_audit(
        db,
        shop_id=shop.id,
        actor_id=current_member.user_id,
        action="BOT_TOKEN_SET",
        entity_type="shop_bot",
        entity_id=bot.id,
        after={"bot_username": body.bot_username, "mode": body.mode, "configured": True},
    )
    await db.commit()

    return ShopBotResponse(
        id=str(bot.id),
        shop_id=str(bot.shop_id),
        bot_username=bot.bot_username,
        mode=bot.mode,
        is_active=bot.is_active,
    )
