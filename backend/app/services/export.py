import json
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Entry
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload


async def export_all_json(db: AsyncSession) -> str:
    result = await db.execute(
        select(Entry).options(
            selectinload(Entry.tags), selectinload(Entry.attachments)
        ).order_by(Entry.updated_at.desc())
    )
    entries = result.scalars().all()

    data = {"version": "1.0", "exported_at": datetime.datetime.utcnow().isoformat(), "entries": []}

    for entry in entries:
        entry_data = {
            "id": entry.id,
            "title": entry.title,
            "content": entry.content,
            "category_id": entry.category_id,
            "is_favorite": entry.is_favorite,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "tags": [t.name for t in entry.tags],
            "attachments": [],
        }
        data["entries"].append(entry_data)

    return json.dumps(data, ensure_ascii=False, indent=2)


async def export_markdown(db: AsyncSession) -> dict[str, list[dict]]:
    result = await db.execute(
        select(Entry).options(
            selectinload(Entry.tags), joinedload(Entry.category)
        ).order_by(Entry.updated_at.desc())
    )
    entries = result.scalars().all()

    by_category: dict[str, list[dict]] = {}
    for entry in entries:
        cat_name = "Other"
        if entry.category:
            cat_name = entry.category.name
        if cat_name not in by_category:
            by_category[cat_name] = []
        by_category[cat_name].append({
            "title": entry.title,
            "content": entry.content,
            "tags": [t.name for t in entry.tags],
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        })

    return by_category
