from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import backup as backup_services

router = APIRouter(prefix="/api", tags=["backup"])


@router.get("/backups", response_model=list[dict])
async def list_backups():
    return await backup_services.get_backup_files()


@router.post("/backups", response_model=dict)
async def create_backup(db: AsyncSession = Depends(get_db)):
    path = await backup_services.create_backup(db)
    return {"path": path, "filename": path.split("/")[-1]}


@router.get("/export/json", response_class=PlainTextResponse)
async def export_json(db: AsyncSession = Depends(get_db)):
    from app.services import export as export_services
    data = await export_services.export_all_json(db)
    return data


@router.get("/export/markdown", response_class=JSONResponse)
async def export_markdown(db: AsyncSession = Depends(get_db)):
    from app.services import export as export_services
    data = await export_services.export_markdown(db)
    result = {}
    for cat, entries in data.items():
        result[cat] = []
        for e in entries:
            md = f"# {e['title']}\n\n"
            if e.get('tags'):
                md += f"Tags: {', '.join(e['tags'])}\n\n"
            md += e['content']
            result[cat].append(md)
    return result
