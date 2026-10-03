from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.modules.inventory.service import InventoryService, InsufficientStockError, ReservationNotFoundError
from app.modules.inventory.models import InventoryItem

router = APIRouter(prefix="/admin/inventory", tags=["Admin: Inventory"])


@router.get("/items/{inventory_id}", response_model=dict)
async def get_inventory_item(inventory_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_id)
    )
    item = result.scalar_one_or_none()
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
