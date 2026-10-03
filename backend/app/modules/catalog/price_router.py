"""
Admin price endpoints — S2-B.

POST /admin/products/{product_id}/price       → set new active price (INV-005)
GET  /admin/products/{product_id}/price        → current active price
GET  /admin/products/{product_id}/price/history → full history

Public catalog endpoints — S2-B.

GET  /catalog/shops/{shop_slug}/products       → active products list with current price
GET  /catalog/shops/{shop_slug}/products/{id}  → product detail card with current price
GET  /catalog/shops/{shop_slug}/categories     → category tree (active only)
"""
import uuid
import logging
from decimal import Decimal
from typing import Optional, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context, require_shop_role
from app.modules.shops.models import Shop, ShopMember
from app.modules.shops.service import ShopService
from app.modules.catalog.models import Product, Category
from app.modules.catalog.price_models import Price
from app.modules.catalog.price_service import PriceService
from app.modules.catalog.service import CatalogService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

# ── Admin price router ─────────────────────────────────────────────────────

admin_price_router = APIRouter(prefix="/admin", tags=["Admin: Prices"])


class PriceSetRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field("RUB", min_length=3, max_length=3)
    variant_id: Optional[str] = None


class PriceResponse(BaseModel):
    id: str
    shop_id: str
    product_id: str
    variant_id: Optional[str]
    amount: str
    currency: str
    valid_from: str
    valid_to: Optional[str]


def _price_to_response(p: Price) -> PriceResponse:
    return PriceResponse(
        id=str(p.id),
        shop_id=str(p.shop_id),
        product_id=str(p.product_id),
        variant_id=str(p.variant_id) if p.variant_id else None,
        amount=str(p.amount),
        currency=p.currency,
        valid_from=p.valid_from.isoformat(),
        valid_to=p.valid_to.isoformat() if p.valid_to else None,
    )


@admin_price_router.post(
    "/products/{product_id}/price",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_product_price(
    product_id: str,
    body: PriceSetRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    INV-005: Closes the current active price (valid_to = now) and inserts a new row.
    The old price is NEVER deleted — full history is preserved.
    INV-011: audit_log is written in the same transaction.
    """
    shop, _ = shop_context
    try:
        prod_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID")

    # IDOR guard: product must belong to this shop
    product = await CatalogService.get_product(db, product_id=prod_uuid, shop_id=shop.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant_uuid: Optional[uuid.UUID] = None
    if body.variant_id:
        try:
            variant_uuid = uuid.UUID(body.variant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid variant_id UUID")
        # IDOR: variant must belong to the same product/shop
        variant = await CatalogService.get_variant(
            db, variant_id=variant_uuid, product_id=prod_uuid, shop_id=shop.id
        )
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")

    new_price = await PriceService.set_price(
        db,
        shop_id=shop.id,
        product_id=prod_uuid,
        variant_id=variant_uuid,
        amount=body.amount,
        currency=body.currency,
        created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(new_price)
    return _price_to_response(new_price)


@admin_price_router.get(
    "/products/{product_id}/price",
    response_model=PriceResponse,
)
async def get_current_price(
    product_id: str,
    variant_id: Optional[str] = Query(None),
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    try:
        prod_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID")

    product = await CatalogService.get_product(db, product_id=prod_uuid, shop_id=shop.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    var_uuid: Optional[uuid.UUID] = None
    if variant_id:
        try:
            var_uuid = uuid.UUID(variant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid variant_id UUID")

    price = await PriceService.get_active_price(
        db, product_id=prod_uuid, variant_id=var_uuid
    )
    if not price:
        raise HTTPException(status_code=404, detail="No active price set")
    return _price_to_response(price)


@admin_price_router.get(
    "/products/{product_id}/price/history",
    response_model=List[PriceResponse],
)
async def get_price_history(
    product_id: str,
    variant_id: Optional[str] = Query(None),
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    try:
        prod_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID")

    product = await CatalogService.get_product(db, product_id=prod_uuid, shop_id=shop.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    var_uuid: Optional[uuid.UUID] = None
    if variant_id:
        try:
            var_uuid = uuid.UUID(variant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid variant_id UUID")

    history = await PriceService.get_price_history(
        db, product_id=prod_uuid, variant_id=var_uuid
    )
    return [_price_to_response(p) for p in history]


# ── Public catalog router ──────────────────────────────────────────────────

catalog_router = APIRouter(prefix="/catalog", tags=["Public: Catalog"])


class PublicPriceInfo(BaseModel):
    amount: str
    currency: str


class PublicProductCard(BaseModel):
    id: str
    name: str
    slug: str
    sku: str
    description: Optional[str]
    is_active: bool
    tags: list
    category_id: Optional[str]
    unit_id: Optional[str]
    current_price: Optional[PublicPriceInfo]


class PublicCategoryNode(BaseModel):
    id: str
    name: str
    slug: str
    sort_order: int
    depth: int
    children: List["PublicCategoryNode"] = Field(default_factory=list)


async def _get_shop_by_slug_or_404(db: AsyncSession, slug: str) -> Shop:
    shop = await ShopService.get_by_slug(db, slug)
    if not shop or not shop.is_active:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


async def _enrich_product(db: AsyncSession, product: Product) -> PublicProductCard:
    price = await PriceService.get_active_price(db, product_id=product.id)
    price_info = None
    if price:
        price_info = PublicPriceInfo(amount=str(price.amount), currency=price.currency)
    return PublicProductCard(
        id=str(product.id),
        name=product.name,
        slug=product.slug,
        sku=product.sku,
        description=product.description,
        is_active=product.is_active,
        tags=product.tags or [],
        category_id=str(product.category_id) if product.category_id else None,
        unit_id=str(product.unit_id) if product.unit_id else None,
        current_price=price_info,
    )


def _build_public_category_tree(categories: list) -> List[PublicCategoryNode]:
    child_map: dict = {}
    for cat in categories:
        if cat.parent_id:
            child_map.setdefault(cat.parent_id, []).append(cat)

    def node(cat: Category) -> PublicCategoryNode:
        children = [node(c) for c in sorted(child_map.get(cat.id, []), key=lambda x: x.sort_order)]
        return PublicCategoryNode(
            id=str(cat.id), name=cat.name, slug=cat.slug,
            sort_order=cat.sort_order, depth=cat.depth, children=children,
        )

    roots = sorted(
        [c for c in categories if c.parent_id is None],
        key=lambda x: x.sort_order,
    )
    return [node(r) for r in roots]


@catalog_router.get(
    "/shops/{shop_slug}/categories",
    response_model=List[PublicCategoryNode],
)
async def public_category_tree(
    shop_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: return active category tree for a shop (no auth required)."""
    shop = await _get_shop_by_slug_or_404(db, shop_slug)
    cats = await CatalogService.list_all_categories(db, shop_id=shop.id)
    active = [c for c in cats if c.is_active]
    return _build_public_category_tree(active)


@catalog_router.get(
    "/shops/{shop_slug}/products",
    response_model=List[PublicProductCard],
)
async def public_product_list(
    shop_slug: str,
    category_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Public: list active products for a shop.
    Optionally filter by category_id.
    Each product includes current_price (valid_to IS NULL).
    """
    shop = await _get_shop_by_slug_or_404(db, shop_slug)

    stmt = (
        select(Product)
        .where(Product.shop_id == shop.id, Product.is_active.is_(True))
        .order_by(Product.name)
    )
    if category_id:
        try:
            cat_uuid = uuid.UUID(category_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category_id UUID")
        stmt = stmt.where(Product.category_id == cat_uuid)

    res = await db.execute(stmt)
    products = res.scalars().all()

    return [await _enrich_product(db, p) for p in products]


@catalog_router.get(
    "/shops/{shop_slug}/products/{product_id}",
    response_model=PublicProductCard,
)
async def public_product_detail(
    shop_slug: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public: product detail card with current price.
    GET /catalog/products/{id} → current price (valid_to IS NULL) — per S2 DoD.
    """
    shop = await _get_shop_by_slug_or_404(db, shop_slug)
    try:
        prod_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID")

    product = await CatalogService.get_product(db, product_id=prod_uuid, shop_id=shop.id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    return await _enrich_product(db, product)
