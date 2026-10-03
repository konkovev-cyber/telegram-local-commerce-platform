from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.shops.models import Shop, ShopMember
from app.modules.inventory.service import InventoryService, InsufficientStockError, ReservationNotFoundError
from app.modules.inventory.models import InventoryItem, InventoryMovement

router = APIRouter(prefix="/admin/inventory", tags=["Admin: Inventory"])


@router.get("", response_model=List[dict])
async def list_inventory_items(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    product_id: Optional[str] = Query(None, description="Filter by product UUID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    shop, _ = shop_context
    pid = None
    if product_id:
        import uuid as _uuid
        try:
            pid = _uuid.UUID(product_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid product_id UUID")

    items = await InventoryService.list_items(db, shop_id=shop.id, product_id=pid, limit=limit, offset=offset)
    return [{
        "id": str(i.id), "shop_id": str(i.shop_id),
        "product_id": str(i.product_id),
        "variant_id": str(i.variant_id) if i.variant_id else None,
        "available_qty": str(i.available_qty),
        "reserved_qty": str(i.reserved_qty),
        "sold_qty": str(i.sold_qty),
    } for i in items]


@router.get("/items/{inventory_id}", response_model=dict)
async def get_inventory_item(
    inventory_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    import uuid as _uuid
    item = await InventoryService.get_item(db, inventory_id=_uuid.UUID(inventory_id), shop_id=shop.id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return {
        "id": str(item.id), "shop_id": str(item.shop_id),
        "product_id": str(item.product_id),
        "variant_id": str(item.variant_id) if item.variant_id else None,
        "available_qty": str(item.available_qty),
        "reserved_qty": str(item.reserved_qty),
        "sold_qty": str(item.sold_qty),
    }


@router.get("/items/{inventory_id}/movements", response_model=List[dict])
async def list_movements(
    inventory_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    shop, _ = shop_context
    import uuid as _uuid
    inv_uuid = _uuid.UUID(inventory_id)
    # Verify ownership
    item = await InventoryService.get_item(db, inventory_id=inv_uuid, shop_id=shop.id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    movements = await InventoryService.list_movements(db, inventory_id=inv_uuid, limit=limit)
    return [{
        "id": str(m.id), "type": m.type, "qty": str(m.qty),
        "before_available": str(m.before_available),
        "after_available": str(m.after_available),
        "note": m.note, "created_at": m.created_at.isoformat(),
    } for m in movements]
