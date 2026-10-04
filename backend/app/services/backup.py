import os
import zipfile
import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import Entry, Category, Attachment
from sqlalchemy import select


async def create_backup(db: AsyncSession) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"sysvault-backup-{timestamp}.zip"
    backup_path = Path(settings.backups_dir) / filename
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", "").replace("./", str(Path.cwd()) + "/"))
    if not db_path.is_absolute():
        db_path = Path(settings.data_dir) / "database.db"

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if db_path.exists():
            zf.write(db_path, "database.db")
        attachments_dir = Path(settings.attachments_dir)
        if attachments_dir.exists():
            for f in attachments_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f"attachments/{f.relative_to(attachments_dir)}")

    return str(backup_path)


async def get_backup_files() -> list[dict]:
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(backups_dir.glob("sysvault-backup-*.zip"), reverse=True):
        files.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created_at": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return files
