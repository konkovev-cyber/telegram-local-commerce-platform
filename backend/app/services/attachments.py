import os
import uuid
import shutil
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Attachment
from app.services.entries import get_entry
from app.config import settings


ALLOWED_MIMES = {
    "text/plain", "text/calendar", "text/csv", "text/xml",
    "text/html", "text/css",
    "application/json", "application/xml", "application/yaml", "application/octet-stream",
    "application/pdf",
    "application/zip", "application/gzip", "application/x-tar",
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
}

ALLOWED_EXTENSIONS = {
    ".txt", ".conf", ".cfg", ".yaml", ".yml", ".json", ".xml",
    ".log", ".md", ".csv",
    ".pdf",
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".zip", ".tar", ".gz",
}


def is_safe_path(base: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def validate_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    if not filename:
        filename = "file"
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"


async def upload_attachment(db: AsyncSession, entry_id: int, file_data: bytes, filename: str, mime_type: str) -> Attachment:
    if mime_type not in ALLOWED_MIMES and not mime_type.startswith("text/") and not mime_type.startswith("image/"):
        mime_type = "application/octet-stream"

    entry_result = await get_entry(db, entry_id)
    if not entry_result:
        raise ValueError("Entry not found")

    if len(file_data) > settings.max_attachment_size:
        raise ValueError(f"File too large (max {settings.max_attachment_size} bytes)")

    safe_name = validate_filename(filename)
    dest_dir = Path(settings.attachments_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name

    if dest_path.exists():
        safe_name = f"{safe_name[:-4]}_{uuid.uuid4().hex[:8]}{os.path.splitext(safe_name)[1]}"
        dest_path = dest_dir / safe_name

    dest_path.write_bytes(file_data)

    attachment = Attachment(
        entry_id=entry_id,
        original_filename=filename,
        stored_filename=safe_name,
        mime_type=mime_type,
        size=len(file_data),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def delete_attachment(db: AsyncSession, attachment_id: int) -> bool:
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    att = result.scalar_one_or_none()
    if not att:
        return False

    file_path = Path(settings.attachments_dir) / att.stored_filename
    if file_path.exists():
        file_path.unlink()

    await db.delete(att)
    await db.commit()
    return True
