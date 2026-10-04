import datetime
import re
from typing import Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Employee, Asset


ASSET_TYPES = ["ПК", "Ноутбук", "МФУ/Принтер", "Монитор", "ИБП", "IP-телефон", "Аналоговый телефон", "Сетевое оборудование", "Прочее"]
ASSET_STATUSES = ["в работе", "в ремонте", "на складе", "списано"]

TYPE_ALIASES = {
    "desktop": "ПК", "пк": "ПК", "компьютер": "ПК",
    "laptop": "Ноутбук", "ноутбук": "Ноутбук", "ноут": "Ноутбук", "macbook": "Ноутбук",
    "printer": "МФУ/Принтер", "мфу": "МФУ/Принтер", "принтер": "МФУ/Принтер",
    "monitor": "Монитор", "монитор": "Монитор",
    "ups": "ИБП", "ибп": "ИБП",
    "ip-телефон": "IP-телефон", "телефон": "IP-телефон", "sip": "IP-телефон", "yealink": "IP-телефон",
    "network": "Сетевое оборудование", "свич": "Сетевое оборудование", "коммутатор": "Сетевое оборудование", "dlink": "Сетевое оборудование",
}


def normalize_type(raw: Optional[str], default: str = "Прочее") -> str:
    if not raw:
        return default
    rl = raw.strip().lower()
    for alias, t in TYPE_ALIASES.items():
        if alias in rl:
            return t
    return raw.strip() or default


# ---------- Employees ----------

async def list_employees(db: AsyncSession, q: str | None = None) -> list[dict]:
    query = select(Employee).order_by(Employee.full_name)
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            Employee.full_name.ilike(like),
            Employee.department.ilike(like),
            Employee.domain_login.ilike(like),
            Employee.email.ilike(like),
        ))
    result = await db.execute(query)
    employees = result.scalars().all()

    counts = await db.execute(
        select(Asset.employee_id, func.count(Asset.id)).group_by(Asset.employee_id)
    )
    count_map = {eid: cnt for eid, cnt in counts.all()}

    return [{
        "id": emp.id,
        "full_name": emp.full_name,
        "department": emp.department,
        "position": emp.position,
        "phone": emp.phone,
        "email": emp.email,
        "sip": emp.sip,
        "domain_login": emp.domain_login,
        "room": emp.room,
        "notes": emp.notes,
        "asset_count": count_map.get(emp.id, 0),
    } for emp in employees]


async def get_employee(db: AsyncSession, employee_id: int) -> Optional[Employee]:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    return result.scalar_one_or_none()


async def create_employee(db: AsyncSession, data: dict) -> Employee:
    emp = Employee(**{k: v for k, v in data.items() if v is not None})
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


async def update_employee(db: AsyncSession, employee_id: int, data: dict) -> Optional[Employee]:
    emp = await get_employee(db, employee_id)
    if not emp:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(emp, k, v)
    await db.commit()
    await db.refresh(emp)
    return emp


async def delete_employee(db: AsyncSession, employee_id: int) -> bool:
    emp = await get_employee(db, employee_id)
    if not emp:
        return False
    await db.delete(emp)
    await db.commit()
    return True


# ---------- Assets ----------

def _asset_dict(a: Asset, emp_name: Optional[str]) -> dict:
    return {
        "id": a.id,
        "asset_type": a.asset_type,
        "vendor": a.vendor,
        "model": a.model,
        "serial_number": a.serial_number,
        "inventory_number": a.inventory_number,
        "mac_address": a.mac_address,
        "ip_address": a.ip_address,
        "status": a.status,
        "location": a.location,
        "employee_id": a.employee_id,
        "employee_name": emp_name,
        "purchase_date": a.purchase_date,
        "notes": a.notes,
    }


async def list_assets(
    db: AsyncSession,
    asset_type: str | None = None,
    status: str | None = None,
    location: str | None = None,
    employee_id: int | None = None,
    q: str | None = None,
    unassigned: bool = False,
) -> list[dict]:
    query = select(Asset)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    if status:
        query = query.where(Asset.status == status)
    if location:
        query = query.where(Asset.location.ilike(f"%{location}%"))
    if employee_id:
        query = query.where(Asset.employee_id == employee_id)
    if unassigned:
        query = query.where(Asset.employee_id.is_(None))
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            Asset.model.ilike(like),
            Asset.vendor.ilike(like),
            Asset.serial_number.ilike(like),
            Asset.inventory_number.ilike(like),
            Asset.mac_address.ilike(like),
            Asset.ip_address.ilike(like),
            Asset.location.ilike(like),
            Asset.notes.ilike(like),
        ))
    query = query.order_by(Asset.asset_type, Asset.vendor, Asset.model)
    result = await db.execute(query)
    assets = result.scalars().all()

    emp_ids = {a.employee_id for a in assets if a.employee_id}
    emp_map = {}
    if emp_ids:
        emps = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e.full_name for e in emps.scalars().all()}

    return [_asset_dict(a, emp_map.get(a.employee_id)) for a in assets]


async def get_asset(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalar_one_or_none()


async def create_asset(db: AsyncSession, data: dict) -> Asset:
    if data.get("asset_type"):
        data["asset_type"] = normalize_type(data["asset_type"])
    asset = Asset(**{k: v for k, v in data.items() if v is not None})
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def update_asset(db: AsyncSession, asset_id: int, data: dict) -> Optional[Asset]:
    asset = await get_asset(db, asset_id)
    if not asset:
        return None
    for k, v in data.items():
        if k == "employee_id" or v is not None:
            setattr(asset, k, v)
    await db.commit()
    await db.refresh(asset)
    return asset


async def delete_asset(db: AsyncSession, asset_id: int) -> bool:
    asset = await get_asset(db, asset_id)
    if not asset:
        return False
    await db.delete(asset)
    await db.commit()
    return True


async def assign_asset(db: AsyncSession, asset_id: int, employee_id: Optional[int]) -> Optional[Asset]:
    asset = await get_asset(db, asset_id)
    if not asset:
        return None
    asset.employee_id = employee_id
    await db.commit()
    await db.refresh(asset)
    return asset


# ---------- Import ----------
# Формат шаблона (12 колонок, разделитель , ; или таб):
# ФИО;Должность;Телефон;Email;SIP;Инв.№;Тип;Производитель;Модель;Серийный;MAC;Кабинет

def _split_line(line: str) -> list[str]:
    for sep in ["\t", ";", ","]:
        if sep in line:
            return [p.strip() for p in line.split(sep)]
    return [line.strip()]


def _is_mac(s: str) -> bool:
    return bool(re.match(r"^[0-9a-fA-F:\-]{12,17}$", s.strip()) and (":" in s or "-" in s))


def _is_ip(s: str) -> bool:
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s.strip()))


def _is_inv(s: str) -> bool:
    s = s.strip()
    if _is_ip(s) or re.match(r"^\d+\.\d+$", s):
        return False
    return bool(re.match(r"^[0-9A-Za-zА-Яа-я\-]{1,12}$", s))


async def import_assets(db: AsyncSession, text: str, default_type: str = "Прочее") -> dict:
    lines = [l for l in text.split("\n") if l.strip()]
    created = 0
    employees_created = 0
    errors = []

    emps = await db.execute(select(Employee))
    emp_map = {e.full_name.lower().strip(): e.id for e in emps.scalars().all()}

    # Detect header row (template format)
    start = 0
    header = None
    if lines and "фио" in lines[0].lower():
        header = [h.strip().lower() for h in _split_line(lines[0])]
        start = 1

    for lineno, line in enumerate(lines[start:], start + 1):
        parts = _split_line(line)
        if len(parts) < 2:
            errors.append(f"Строка {lineno}: слишком мало полей")
            continue

        full_name = position = phone = email = sip = None
        inv = atype = vendor = model = serial = mac = location = None

        if header:
            def col(*names):
                for n in names:
                    for i, h in enumerate(header):
                        if n in h and i < len(parts) and parts[i]:
                            return parts[i]
                return None
            full_name = col("фио")
            position = col("должность")
            phone = col("телефон")
            email = col("email", "почт")
            sip = col("sip")
            inv = col("инвентарный", "инв")
            atype = col("тип")
            vendor = col("производитель", "vendor")
            model = col("модель", "model")
            serial = col("серийный", "serial")
            mac = col("mac")
            location = col("кабинет", "отдел", "место")
        else:
            for p in parts:
                pl = p.lower()
                if _is_mac(p) and not mac:
                    mac = p
                elif _is_ip(p) and not location and "ip" in line.lower():
                    location = p
                elif "@" in p and not email:
                    email = p
                elif re.match(r"^\+?[\d][\d\s\-\(\)]{7,}$", p) and not phone:
                    phone = p
                elif _is_inv(p) and inv is None:
                    inv = p
                elif not full_name and re.match(r"^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+", p):
                    full_name = p
                elif ("этаж" in pl or "каб" in pl or "рашпил" in pl or "бабуш" in pl) and not location:
                    location = p
                elif not model and re.match(r"^[A-ZА-Я]", p) and len(p) > 2 and " " not in p[:1]:
                    model = p
                elif not vendor and re.match(r"^[A-Z][a-z]+$", p):
                    vendor = p
            atype = parts[0] if len(parts[0]) < 30 else default_type

        atype = normalize_type(atype, default_type)

        employee_id = None
        if full_name:
            key = full_name.lower().strip()
            if key not in emp_map:
                emp = Employee(
                    full_name=full_name, position=position,
                    phone=phone, email=email, sip=sip,
                )
                db.add(emp)
                await db.flush()
                emp_map[key] = emp.id
                employees_created += 1
            employee_id = emp_map[key]

        if not any([model, vendor, inv, serial, mac]):
            errors.append(f"Строка {lineno}: не распознаны поля техники")
            continue

        db.add(Asset(
            asset_type=atype, vendor=vendor, model=model,
            serial_number=serial, inventory_number=inv,
            mac_address=mac if mac and _is_mac(mac) else None,
            status="в работе", location=location,
            employee_id=employee_id,
        ))
        created += 1

    await db.commit()
    return {"created": created, "employees_created": employees_created, "errors": errors}
