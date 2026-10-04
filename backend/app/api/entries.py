from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import entries as entry_services
from app.schemas import (
    EntryCreate, EntryUpdate, EntryRead,
    CategoryCreate, CategoryUpdate, CategoryRead,
    TagRead, ImportResult, EntryHistoryRead
)
from app.models import Category as CategoryModel


router = APIRouter(prefix="/api", tags=["entries"])


@router.get("/entries", response_model=list[EntryRead])
async def list_entries(
    category_id: int | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    ents, total = await entry_services.get_entries(
        db, category_id=category_id, tag_name=tag,
        favorite=favorite, search=search, limit=limit, offset=offset,
    )
    return ents


@router.get("/entries/search")
async def search_entries(
    q: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    ents, total = await entry_services.search_entries(db, q, limit=limit)
    return {"entries": ents, "total": total}


@router.get("/entries/{entry_id}", response_model=EntryRead)
async def get_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    entry = await entry_services.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/entries", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(data: EntryCreate, db: AsyncSession = Depends(get_db)):
    return await entry_services.create_entry(db, data)


@router.put("/entries/{entry_id}", response_model=EntryRead)
async def update_entry(entry_id: int, data: EntryUpdate, db: AsyncSession = Depends(get_db)):
    entry = await entry_services.update_entry(db, entry_id, data)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    ok = await entry_services.delete_entry(db, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.get("/entries/{entry_id}/history", response_model=list[EntryHistoryRead])
async def get_history(entry_id: int, db: AsyncSession = Depends(get_db)):
    return await entry_services.get_entry_history(db, entry_id)


@router.post("/entries/{entry_id}/restore/{history_id}", response_model=EntryRead)
async def restore_version(entry_id: int, history_id: int, db: AsyncSession = Depends(get_db)):
    entry = await entry_services.restore_entry_version(db, entry_id, history_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    return entry


@router.post("/import/txt", response_model=ImportResult)
async def import_txt(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    return await entry_services.import_txt(db, data.get("content", ""), data.get("category_id"), data.get("separator"))
