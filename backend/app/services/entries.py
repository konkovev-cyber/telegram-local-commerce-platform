import os
import uuid
import re
import datetime
from typing import Optional, List
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Entry, Category, Tag, EntryTag, Attachment, EntryHistory
from app.schemas import (
    EntryCreate, EntryUpdate, EntryRead, TagRead, AttachmentRead,
    EntryHistoryRead, ImportResult
)
from app.config import settings


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text[:50]


async def seed_categories(db: AsyncSession):
    default_categories = [
        "Servers", "Network", "Linux", "Windows", "Docker",
        "Synology", "Domains", "Commands", "Problems",
        "Instructions", "Checklists", "Notes", "Other"
    ]
    for name in default_categories:
        existing = await db.execute(select(Category).where(Category.name == name))
        if not existing.scalar_one_or_none():
            cat = Category(name=name, slug=slugify(name))
            db.add(cat)
    await db.commit()


async def seed_entries(db: AsyncSession):
    server_cat = await db.execute(select(Category.id).where(Category.name == "Servers"))
    server_id = server_cat.scalar_one_or_none()
    docker_cat = await db.execute(select(Category.id).where(Category.name == "Docker"))
    docker_id = docker_cat.scalar_one_or_none()
    commands_cat = await db.execute(select(Category.id).where(Category.name == "Commands"))
    commands_id = commands_cat.scalar_one_or_none()
    network_cat = await db.execute(select(Category.id).where(Category.name == "Network"))
    network_id = network_cat.scalar_one_or_none()
    synology_cat = await db.execute(select(Category.id).where(Category.name == "Synology"))
    synology_id = synology_cat.scalar_one_or_none()
    notes_cat = await db.execute(select(Category.id).where(Category.name == "Notes"))
    notes_id = notes_cat.scalar_one_or_none()

    existing = await db.execute(select(Entry).limit(1))
    if existing.scalar_one_or_none():
        return

    sample_entries = [
        {
            "title": "Docker cleanup",
            "content": "# Docker cleanup\n\n## Проверка\n\n```bash\ndocker ps\ndocker system df\n```\n\n## Очистка\n\n```bash\n# Free disk space\ndocker system prune\n\n# Remove unused volumes\ndocker volume prune\n\n# Remove unused images\ndocker image prune -a\n```\n\n> Важно: не удалять volumes с данными!",
            "category_id": docker_id,
            "is_favorite": True,
        },
        {
            "title": "Nginx reverse proxy",
            "content": "# Nginx reverse proxy configuration\n\n## Basic config\n\n```nginx\nserver {\n    listen 80;\n    server_name example.com;\n\n    location / {\n        proxy_pass http://localhost:3000;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    }\n}\n```\n\n## SSL with Let's Encrypt\n\n```bash\n Certbot certonly --nginx -d example.com\n```",
            "category_id": commands_id,
            "is_favorite": False,
        },
        {
            "title": "Server srv-web-01",
            "content": "## Server Info\n\n- **IP:** 192.168.1.20\n- **Hostname:** srv-web-01\n- **OS:** Debian 12\n- **Purpose:** Web server (nginx + Node.js)\n- **RAM:** 4GB\n- **CPU:** 2 vCore\n\n## Services\n\n- nginx (port 80/443)\n- Node.js app (port 3000)\n- PostgreSQL (port 5432)\n\n## Access\n\n```bash\nssh admin@192.168.1.20\n```\n\n**Password:** see LastPass → srv-web-01",
            "category_id": server_id,
            "is_favorite": True,
        },
        {
            "title": "Synology backup",
            "content": "# Synology Backup Procedures\n\n## Backup tasks\n\n1. **System config**: Control Panel → Update & Restore → Backup/Restore\n2. **Shared folders**: Use Hyper Backup\n3. **Snapshot replication**: for critical data\n\n## Commands\n\n```bash\n# Check storage\nsynoguard check\n\n# View logs\nlogread | grep backup\n\n# Run snapshot\n/snapschelper.sh --snapshot --volume vol1\n```\n\n## Recovery\n\n1. DSM → Hyper Backup → Restore\n2. Or use snapshot via File Station",
            "category_id": synology_id,
            "is_favorite": False,
        },
        {
            "title": "VPN configuration",
            "content": "# VPN Configuration\n\n## OpenVPN Server (on firewall)\n\n- **Address:** vpn.internal.local\n- **Port:** 1194/udp\n- **Subnet:** 10.8.0.0/24\n\n## Client config\n\n```bash\n# Generate client cert\nopenvpn --genkey --secret keys/client1.key\n\n# Export config\nscp user@vpn:/etc/openvpn/client1.ovpn .\n```\n\n## WireGuard\n\n```bash\nwg genkey | wg pubkey > public.key\nwg genkey > private.key\nwg set wg0 peer <pubkey> allowed-ips 10.6.0.2\n```",
            "category_id": network_id,
            "is_favorite": False,
        },
        {
            "title": "Useful Linux commands",
            "content": "# Useful Linux Commands\n\n## System info\n\n```bash\n# CPU and memory\nhtop\ncat /proc/cpuinfo\nfree -h\n\n# Disk usage\ndf -h\ndu -sh /var/log\n\n# Network\nip addr show\nss -tlnp\nnetstat -rn\n```\n\n## Process management\n\n```bash\n# Kill by name\npkill -f \"process_name\"\n\n# Find and kill\npgrep -f \"pattern\" | xargs kill -9\n\n# Check resources\nps aux --sort=-%mem | head -20\n```\n\n## Log analysis\n\n```bash\n# Recent errors\ngrep -i \"error\\|fail\\|denied\" /var/log/syslog | tail -50\n\n# Watch logs\njournalctl -f -u nginx\n```\n\n## File operations\n\n```bash\n# Find large files\nfind / -type f -size +100M 2>/dev/null\n\n# Find by content\ngrep -rl \"pattern\" /etc/\n\n# Safe replace\nsed -i 's/old/new/g' file.conf\n```",
            "category_id": commands_id,
            "is_favorite": True,
        },
    ]

    for entry_data in sample_entries:
        entry = Entry(**entry_data)
        db.add(entry)

    await db.commit()


async def get_entries(
    db: AsyncSession,
    category_id: Optional[int] = None,
    tag_name: Optional[str] = None,
    favorite: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[EntryRead], int]:
    query = select(Entry).join(Category, isouter=True)

    if category_id:
        query = query.where(Entry.category_id == category_id)
    if favorite is not None:
        query = query.where(Entry.is_favorite == favorite)
    if search:
        terms = search.strip().lower().split()
        conditions = [
            Entry.title.ilike(f"%{term}%") |
            Entry.content.ilike(f"%{term}%")
        ]
        if tag_name:
            conditions.append(Tag.name.ilike(tag_name.lower()))
        query = query.where(or_(*conditions))
        if tag_name:
            query = query.join(Entry.tags).where(Tag.name.ilike(tag_name.lower()))
    else:
        if tag_name:
            query = query.join(Entry.tags).where(Tag.name.ilike(tag_name.lower()))

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(Entry.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    entries = result.scalars().all()

    out = []
    for entry in entries:
        tags = await db.execute(
            select(Tag).join(EntryTag).where(EntryTag.entry_id == entry.id)
        )
        attachments = await db.execute(
            select(Attachment).where(Attachment.entry_id == entry.id)
        )
        cat_result = await db.execute(select(Category).where(Category.id == entry.category_id)) if entry.category_id else None
        cat = cat_result.scalar_one_or_none() if cat_result else None

        out.append(EntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            category_id=entry.category_id,
            category_name=cat.name if cat else None,
            is_favorite=entry.is_favorite,
            tags=[TagRead(id=t.id, name=t.name) for t in tags.scalars().all()],
            attachments=[AttachmentRead(**{k: getattr(a, k) for k in AttachmentRead.model_fields}) for a in attachments.scalars().all()],
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        ))

    return out, total


async def get_entry(db: AsyncSession, entry_id: int) -> Optional[EntryRead]:
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return None

    tags = await db.execute(select(Tag).join(EntryTag).where(EntryTag.entry_id == entry.id))
    attachments = await db.execute(select(Attachment).where(Attachment.entry_id == entry.id))
    cat_result = await db.execute(select(Category).where(Category.id == entry.category_id)) if entry.category_id else None
    cat = cat_result.scalar_one_or_none() if cat_result else None

    return EntryRead(
        id=entry.id,
        title=entry.title,
        content=entry.content,
        category_id=entry.category_id,
        category_name=cat.name if cat else None,
        is_favorite=entry.is_favorite,
        tags=[TagRead(id=t.id, name=t.name) for t in tags.scalars().all()],
        attachments=[AttachmentRead(**{k: getattr(a, k) for k in AttachmentRead.model_fields}) for a in attachments.scalars().all()],
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def create_entry(db: AsyncSession, data: EntryCreate) -> EntryRead:
    entry = Entry(
        title=data.title,
        content=data.content,
        category_id=data.category_id,
        is_favorite=data.is_favorite,
    )
    db.add(entry)
    await db.flush()

    if data.tags:
        for tag_name in data.tags:
            tag = await db.execute(select(Tag).where(Tag.name == tag_name.lower()))
            tag_obj = tag.scalar_one_or_none()
            if not tag_obj:
                tag_obj = Tag(name=tag_name.lower())
                db.add(tag_obj)
                await db.flush()
            et = EntryTag(entry_id=entry.id, tag_id=tag_obj.id)
            db.add(et)

    await db.commit()
    await db.refresh(entry)
    return await get_entry(db, entry.id)


async def update_entry(db: AsyncSession, entry_id: int, data: EntryUpdate) -> Optional[EntryRead]:
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return None

    # Save to history before updating
    hist = EntryHistory(
        entry_id=entry.id,
        title=entry.title,
        content=entry.content,
    )
    db.add(hist)
    await db.flush()

    if data.title is not None:
        entry.title = data.title
    if data.content is not None:
        entry.content = data.content
    if data.category_id is not None:
        entry.category_id = data.category_id
    if data.is_favorite is not None:
        entry.is_favorite = data.is_favorite
    if data.tags is not None:
        existing_tags = await db.execute(
            select(Tag).join(EntryTag).where(EntryTag.entry_id == entry.id)
        )
        old_tag_ids = {t.id for t in existing_tags.scalars().all()}

        new_tags = []
        for tag_name in data.tags:
            tag = await db.execute(select(Tag).where(Tag.name == tag_name.lower()))
            tag_obj = tag.scalar_one_or_none()
            if not tag_obj:
                tag_obj = Tag(name=tag_name.lower())
                db.add(tag_obj)
                await db.flush()
                db.refresh(tag_obj)
            new_tags.append(tag_obj.id)

        to_remove = old_tag_ids - set(new_tags)
        for tid in to_remove:
            await db.execute(
                text("DELETE FROM entry_tags WHERE entry_id = :eid AND tag_id = :tid")
                .bindparams(eid=entry.id, tid=tid)
            )
        to_add = set(new_tags) - old_tag_ids
        for tid in to_add:
            et = EntryTag(entry_id=entry.id, tag_id=tid)
            db.add(et)

    await db.commit()
    await db.refresh(entry)
    return await get_entry(db, entry.id)


async def delete_entry(db: AsyncSession, entry_id: int) -> bool:
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    await db.delete(entry)
    await db.commit()
    return True


async def get_categories(db: AsyncSession) -> List[Category]:
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


async def create_category(db: AsyncSession, name: str) -> Category:
    cat = Category(name=name, slug=slugify(name))
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def update_category(db: AsyncSession, category_id: int, name: str) -> Optional[Category]:
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        return None
    cat.name = name
    cat.slug = slugify(name)
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, category_id: int, new_category_id: Optional[int] = None) -> bool:
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        return False

    if new_category_id and new_category_id != category_id:
        await db.execute(
            text("UPDATE entries SET category_id = :new_cat WHERE category_id = :old_cat")
            .bindparams(new_cat=new_category_id, old_cat=category_id)
        )

    await db.delete(cat)
    await db.commit()
    return True


async def get_tags(db: AsyncSession) -> List[Tag]:
    result = await db.execute(select(Tag).order_by(Tag.name))
    return result.scalars().all()


async def get_entry_history(db: AsyncSession, entry_id: int) -> List[EntryHistoryRead]:
    result = await db.execute(
        select(EntryHistory).where(EntryHistory.entry_id == entry_id).order_by(EntryHistory.created_at.desc())
    )
    return [EntryHistoryRead(**{k: getattr(h, k) for k in EntryHistoryRead.model_fields}) for h in result.scalars().all()]


async def restore_entry_version(db: AsyncSession, entry_id: int, history_id: int) -> Optional[EntryRead]:
    result = await db.execute(select(EntryHistory).where(
        EntryHistory.id == history_id,
        EntryHistory.entry_id == entry_id
    ))
    hist = result.scalar_one_or_none()
    if not hist:
        return None

    entry_result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_result.scalar_one_or_none()
    if not entry:
        return None

    entry.title = hist.title
    entry.content = hist.content
    entry.updated_at = datetime.datetime.utcnow()

    old_hist = EntryHistory(entry_id=entry.id, title=entry.title, content=entry.content)
    db.add(old_hist)

    await db.commit()
    await db.refresh(entry)
    return await get_entry(db, entry.id)


async def search_entries(db: AsyncSession, query: str, limit: int = 50) -> tuple[List[EntryRead], int]:
    if not query.strip():
        return [], 0

    terms = query.strip().lower().split()
    conditions = []
    for term in terms:
        conditions.append(
            or_(
                Entry.title.ilike(f"%{term}%"),
                Entry.content.ilike(f"%{term}%"),
            )
        )

    result = await db.execute(
        select(Entry)
        .where(and_(*conditions))
        .order_by(Entry.updated_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(
            select(Entry).where(and_(*conditions)).subquery()
        )
    )
    total = count_result.scalar_one()

    out = []
    for entry in entries:
        tags = await db.execute(
            select(Tag).join(EntryTag).where(EntryTag.entry_id == entry.id)
        )
        attachments = await db.execute(
            select(Attachment).where(Attachment.entry_id == entry.id)
        )
        cat_result = await db.execute(select(Category).where(Category.id == entry.category_id)) if entry.category_id else None
        cat = cat_result.scalar_one_or_none() if cat_result else None

        out.append(EntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            category_id=entry.category_id,
            category_name=cat.name if cat else None,
            is_favorite=entry.is_favorite,
            tags=[TagRead(id=t.id, name=t.name) for t in tags.scalars().all()],
            attachments=[AttachmentRead(**{k: getattr(a, k) for k in AttachmentRead.model_fields}) for a in attachments.scalars().all()],
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        ))

    return out, total


async def import_txt(db: AsyncSession, content: str, category_id: Optional[int] = None, separator: Optional[str] = None) -> ImportResult:
    created = 0
    entries_list = []

    if separator:
        parts = content.split(separator)
    else:
        parts = [content]

    for part in parts:
        part = part.strip()
        if not part:
            continue

        lines = part.split("\n")
        title = ""
        body_lines = []
        title_found = False

        for line in lines:
            stripped = line.strip()
            if not title_found and stripped:
                if stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                else:
                    title = stripped
                title_found = True
            elif title_found:
                body_lines.append(line)

        if not title:
            title = f"Imported entry {created + 1}"

        body = "\n".join(body_lines).strip()
        if not body:
            body = part

        entry_data = EntryCreate(title=title, content=body, category_id=category_id)
        entry = await create_entry(db, entry_data)
        created += 1
        entries_list.append(entry)

    return ImportResult(created=created, entries=entries_list)


async def get_attachment(db: AsyncSession, attachment_id: int) -> Optional[Attachment]:
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    return result.scalar_one_or_none()
