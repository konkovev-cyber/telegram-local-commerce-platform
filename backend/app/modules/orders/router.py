from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.core.db import get_db
from app.modules.auth.dependencies import get_shop_context
from app.modules.shops.models import Shop, ShopMember
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.service import OrderService

router = APIRouter(prefix="/admin/orders", tags=["Admin: Orders"])


@router.get("", response_model=List[dict])
async def list_orders(
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = None,
):
    shop, _ = shop_context
    orders = await OrderService.list_orders(db, shop_id=shop.id, status=status_filter)
    return [{"id": str(o.id), "number": o.number, "status": o.order_status,
             "total": str(o.total), "currency": o.currency} for o in orders]


@router.get("/{order_id}", response_model=dict)
async def get_order(
    order_id: str,
    shop_context=Depends(get_shop_context),
    db: AsyncSession = Depends(get_db),
):
    shop, _ = shop_context
    order = await OrderService.get_order(db, order_id=__import__('uuid').UUID(order_id), shop_id=shop.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"id": str(order.id), "number": order.number, "status": order.order_status,
            "total": str(order.total), "currency": order.currency}
