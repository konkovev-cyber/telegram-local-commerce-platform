from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.services import entries as entry_services
from app.schemas import CategoryCreate, CategoryUpdate, CategoryRead
from app.models import Category as CategoryModel


router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(db: AsyncSession = Depends(get_db)):
    cats = await entry_services.get_categories(db)
    out = []
    for cat in cats:
        count_result = await db.execute(
            select(func.count()).select_from(CategoryModel).where(CategoryModel.id == cat.id)
        )
        # We need entries count per category
        from app.models import Entry
        entry_cnt = await db.execute(
            select(func.count()).select_from(Entry).where(Entry.category_id == cat.id)
        )
        out.append(CategoryRead(id=cat.id, name=cat.name, slug=cat.slug, entry_count=entry_cnt.scalar_one()))
    return out


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(CategoryModel).where(CategoryModel.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category already exists")
    cat = await entry_services.create_category(db, data.name)
    return CategoryRead(id=cat.id, name=cat.name, slug=cat.slug, entry_count=0)


@router.put("/{category_id}", response_model=CategoryRead)
async def update_category(category_id: int, data: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    cat = await entry_services.update_category(db, category_id, data.name)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoryRead(id=cat.id, name=cat.name, slug=cat.slug, entry_count=0)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    new_category_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    ok = await entry_services.delete_category(db, category_id, new_category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Category not found")
