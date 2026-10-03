from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.shops.router import router as shops_router
from app.modules.catalog.router import router as catalog_admin_router
from app.modules.catalog.price_router import admin_price_router, catalog_router as public_catalog_router
from app.modules.inventory.router import router as inventory_router
from app.modules.geo.router import router as geo_router
from app.modules.waves.router import router as waves_router
from app.modules.orders.router import router as orders_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(auth_router)
api_router.include_router(shops_router)
api_router.include_router(catalog_admin_router)
api_router.include_router(admin_price_router)
api_router.include_router(public_catalog_router)
api_router.include_router(inventory_router)
api_router.include_router(geo_router)
api_router.include_router(waves_router)
api_router.include_router(orders_router)
