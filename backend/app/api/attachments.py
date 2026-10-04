from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.services import entries as entry_services, attachments as att_services
from app.schemas import AttachmentRead, TagRead
from app.models import Attachment, Entry
from app.config import settings
from pathlib import Path
import mimetypes

router = APIRouter(prefix="/api", tags=["attachments"])

ALLOWED_MIME_PREFIXES = (
    "text/", "application/json", "application/xml", "application/pdf",
    "application/zip", "application/gzip", "application/x-tar",
    "image/", "application/octet-stream",
)


@router.get("/tags", response_model=list[TagRead])
async def list_tags(db: AsyncSession = Depends(get_db)):
    from app.models import Tag
    result = await db.execute(select(Tag).order_by(Tag.name))
    return result.scalars().all()


@router.post("/entries/{entry_id}/attachments", response_model=AttachmentRead, status_code=201)
async def upload_attachment(
    entry_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.execute(select(Entry).where(Entry.id == entry_id))
    if not entry.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Entry not found")

    file_data = await file.read()
    filename = file.filename or "attachment"
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        attachment = await att_services.upload_attachment(db, entry_id, file_data, filename, mime)
        return attachment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/attachments/{attachment_id}", response_class=FileResponse)
async def download_attachment(attachment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = Path(settings.attachments_dir) / att.stored_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=att.original_filename,
        media_type=att.mime_type,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(attachment_id: int, db: AsyncSession = Depends(get_db)):
    ok = await att_services.delete_attachment(db, attachment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Attachment not found")
