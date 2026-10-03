import logging
import uuid
from typing import Tuple, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user, get_shop_context, require_shop_role
from app.modules.auth.models import User
from app.modules.shops.models import Shop, ShopMember
from app.modules.catalog.models import Unit, Category, Product, ProductVariant
from app.modules.catalog.service import CatalogService
from app.modules.catalog.schemas import (
    UnitCreateRequest, UnitResponse,
    CategoryCreateRequest, CategoryNode,
    ProductCreateRequest, ProductUpdateRequest,
    VariantCreateRequest, VariantResponse,
)
from app.modules.audit.service import write_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin: Catalog"])


def _unit_to_response(unit: Unit) -> UnitResponse:
    return UnitResponse(
        id=str(unit.id), shop_id=str(unit.shop_id),
        name=unit.name, short_name=unit.short_name,
    )


def _build_category_tree(categories: List[Category]) -> List[CategoryNode]:
    by_id = {cat.id: cat for cat in categories}
    roots = [cat for cat in categories if cat.parent_id is None]
    child_map: dict = {}
    for cat in categories:
        if cat.parent_id:
            child_map.setdefault(cat.parent_id, []).append(cat)

    def node(cat: Category) -> CategoryNode:
        children = [node(c) for c in child_map.get(cat.id, [])]
        return CategoryNode(
            id=str(cat.id), shop_id=str(cat.shop_id),
            parent_id=str(cat.parent_id) if cat.parent_id else None,
            name=cat.name, slug=cat.slug, sort_order=cat.sort_order,
            is_active=cat.is_active, depth=cat.depth, children=children,
        )
    return [node(r) for r in roots]


def _product_to_dict(p: Product) -> dict:
    return {
        "id": str(p.id), "shop_id": str(p.shop_id), "name": p.name,
        "slug": p.slug, "sku": p.sku, "barcode": p.barcode,
        "description": p.description, "is_active": p.is_active,
        "tags": p.tags,
        "category_id": str(p.category_id) if p.category_id else None,
        "unit_id": str(p.unit_id) if p.unit_id else None,
    }


def _variant_to_response(v: ProductVariant) -> VariantResponse:
    return VariantResponse(
        id=str(v.id), shop_id=str(v.shop_id), product_id=str(v.product_id),
        name=v.name, sku=v.sku, barcode=v.barcode,
        qty_value=float(v.qty_value) if v.qty_value is not None else None,
        sort_order=v.sort_order, is_active=v.is_active,
    )


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: UnitCreateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    try:
        unit = await CatalogService.create_unit(db, shop_id=shop.id, name=body.name, short_name=body.short_name)
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="UNIT_CREATED", entity_type="unit", entity_id=unit.id, after={"name": unit.name, "short_name": unit.short_name})
        await db.commit()
        return _unit_to_response(unit)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.get("/units", response_model=List[UnitResponse])
async def list_units(
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    units = await CatalogService.list_units(db, shop_id=shop.id)
    return [_unit_to_response(u) for u in units]


@router.post("/categories", response_model=CategoryNode, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    try:
        parent_id = uuid.UUID(body.parent_id) if body.parent_id else None
        category = await CatalogService.create_category(db, shop_id=shop.id, name=body.name, slug=body.slug, parent_id=parent_id, sort_order=body.sort_order)
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="CATEGORY_CREATED", entity_type="category", entity_id=category.id, after={"name": category.name, "slug": category.slug, "depth": category.depth})
        await db.commit()
        # Rebuild full tree from all categories so the new node appears under its parent
        all_cats = await CatalogService.list_all_categories(db, shop_id=shop.id)
        tree = _build_category_tree(all_cats)
        created_id = str(category.id)
        queue = list(tree)
        while queue:
            node = queue.pop(0)
            if node.id == created_id:
                return node
            queue.extend(node.children)
        return tree[0] if tree else CategoryNode(id=created_id, shop_id=str(shop.id), parent_id=str(parent_id) if parent_id else None, name=category.name, slug=category.slug, sort_order=category.sort_order, is_active=category.is_active, depth=category.depth, children=[])
    except ValueError as e:
        msg = str(e)
        if msg in ("self_parent", "cycle"):
            raise HTTPException(status_code=400, detail="Invalid parent: cycle detected")
        if msg == "depth_exceeded":
            raise HTTPException(status_code=400, detail="Depth exceeds maximum of 3")
        if msg == "invalid_parent":
            raise HTTPException(status_code=403, detail="Parent category does not belong to this shop")
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.get("/categories", response_model=List[CategoryNode])
async def list_categories(
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    roots = await CatalogService.list_categories(db, shop_id=shop.id)
    return _build_category_tree(roots)


@router.patch("/categories/{category_id}", response_model=CategoryNode)
async def update_category(
    category_id: str,
    body: CategoryCreateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    cat_uuid = uuid.UUID(category_id)
    category = await db.get(Category, cat_uuid)
    if not category or category.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Category not found")
    before = {"name": category.name, "slug": category.slug, "parent_id": str(category.parent_id) if category.parent_id else None}
    try:
        if body.name is not None:
            category.name = body.name
        if body.slug is not None:
            category.slug = body.slug
        if body.sort_order is not None:
            category.sort_order = body.sort_order
        new_parent_id = uuid.UUID(body.parent_id) if body.parent_id else None
        if new_parent_id != category.parent_id:
            category = await CatalogService.relocate_subtree(db, category_id=category.id, shop_id=shop.id, new_parent_id=new_parent_id)
        after = {"name": category.name, "slug": category.slug, "parent_id": str(category.parent_id) if category.parent_id else None, "depth": category.depth}
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="CATEGORY_UPDATED", entity_type="category", entity_id=category.id, before=before, after=after)
        await db.commit()
        # Rebuild full tree so relocated node appears with correct depth
        all_cats = await CatalogService.list_all_categories(db, shop_id=shop.id)
        tree = _build_category_tree(all_cats)
        created_id = str(category.id)
        queue = list(tree)
        while queue:
            node = queue.pop(0)
            if node.id == created_id:
                return node
            queue.extend(node.children)
        return tree[0] if tree else CategoryNode(id=created_id, shop_id=str(shop.id), parent_id=str(category.parent_id) if category.parent_id else None, name=category.name, slug=category.slug, sort_order=category.sort_order, is_active=category.is_active, depth=category.depth, children=[])
    except ValueError as e:
        msg = str(e)
        if msg in ("self_parent", "cycle"):
            raise HTTPException(status_code=400, detail="Invalid parent: cycle detected")
        if msg == "depth_exceeded":
            raise HTTPException(status_code=400, detail="Depth exceeds maximum of 3")
        if msg == "invalid_parent":
            raise HTTPException(status_code=403, detail="Parent category does not belong to this shop")
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.post("/products", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    try:
        category_id = uuid.UUID(body.category_id) if body.category_id else None
        unit_id = uuid.UUID(body.unit_id) if body.unit_id else None
        product = await CatalogService.create_product(db, shop_id=shop.id, name=body.name, slug=body.slug, sku=body.sku, barcode=body.barcode, description=body.description, category_id=category_id, unit_id=unit_id, tags=body.tags)
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="PRODUCT_CREATED", entity_type="product", entity_id=product.id, after={"name": product.name, "sku": product.sku})
        await db.commit()
        return _product_to_dict(product)
    except ValueError as e:
        msg = str(e)
        if msg == "invalid_category":
            raise HTTPException(status_code=403, detail="Category does not belong to this shop")
        if msg == "invalid_unit":
            raise HTTPException(status_code=403, detail="Unit does not belong to this shop")
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.get("/products", response_model=List[dict])
async def list_products(
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    products = await CatalogService.list_products(db, shop_id=shop.id)
    return [_product_to_dict(p) for p in products]


@router.get("/products/{product_id}", response_model=dict)
async def get_product(
    product_id: str,
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    product = await CatalogService.get_product(db, product_id=uuid.UUID(product_id), shop_id=shop.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_to_dict(product)


@router.patch("/products/{product_id}", response_model=dict)
async def update_product(
    product_id: str,
    body: ProductUpdateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    product = await CatalogService.get_product(db, product_id=uuid.UUID(product_id), shop_id=shop.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    before = _product_to_dict(product)
    try:
        product = await CatalogService.update_product(db, product=product, name=body.name, slug=body.slug, sku=body.sku, barcode=body.barcode, description=body.description, category_id=body.category_id, unit_id=body.unit_id, is_active=body.is_active, tags=body.tags)
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="PRODUCT_UPDATED", entity_type="product", entity_id=product.id, before=before, after=_product_to_dict(product))
        await db.commit()
        return _product_to_dict(product)
    except ValueError as e:
        msg = str(e)
        if msg == "invalid_category":
            raise HTTPException(status_code=403, detail="Category does not belong to this shop")
        if msg == "invalid_unit":
            raise HTTPException(status_code=403, detail="Unit does not belong to this shop")
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.post("/products/{product_id}/variants", response_model=VariantResponse, status_code=status.HTTP_201_CREATED)
async def create_variant(
    product_id: str,
    body: VariantCreateRequest,
    shop_context: Tuple[Shop, ShopMember] = Depends(require_shop_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop, member = shop_context
    try:
        variant = await CatalogService.create_variant(db, shop_id=shop.id, product_id=uuid.UUID(product_id), name=body.name, sku=body.sku, barcode=body.barcode, qty_value=body.qty_value, sort_order=body.sort_order)
        await write_audit(db, shop_id=shop.id, actor_id=member.user_id, action="VARIANT_CREATED", entity_type="product_variant", entity_id=variant.id, after={"name": variant.name, "sku": variant.sku})
        await db.commit()
        return _variant_to_response(variant)
    except ValueError as e:
        if str(e) == "invalid_product":
            raise HTTPException(status_code=403, detail="Product does not belong to this shop")
        raise
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=CatalogService.handle_integrity_error(e))


@router.get("/products/{product_id}/variants", response_model=List[VariantResponse])
async def list_variants(
    product_id: str,
    shop_context: Tuple[Shop, ShopMember] = Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    variants = await CatalogService.list_variants(db, product_id=uuid.UUID(product_id), shop_id=shop.id)
    return [_variant_to_response(v) for v in variants]
