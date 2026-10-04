from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import inventory as inv

router = APIRouter(prefix="/api", tags=["inventory"])


# ---------- Employees ----------

@router.get("/employees")
async def get_employees(q: str | None = None, db: AsyncSession = Depends(get_db)):
    return await inv.list_employees(db, q)


@router.post("/employees", status_code=201)
async def post_employee(data: dict, db: AsyncSession = Depends(get_db)):
    if not data.get("full_name"):
        raise HTTPException(400, "full_name обязателен")
    emp = await inv.create_employee(db, data)
    return {"id": emp.id, "full_name": emp.full_name}


@router.put("/employees/{employee_id}")
async def put_employee(employee_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    emp = await inv.update_employee(db, employee_id, data)
    if not emp:
        raise HTTPException(404, "Сотрудник не найден")
    return {"id": emp.id, "full_name": emp.full_name}


@router.delete("/employees/{employee_id}", status_code=204)
async def del_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    ok = await inv.delete_employee(db, employee_id)
    if not ok:
        raise HTTPException(404, "Сотрудник не найден")


@router.get("/employees/{employee_id}/assets")
async def employee_assets(employee_id: int, db: AsyncSession = Depends(get_db)):
    return await inv.list_assets(db, employee_id=employee_id)


# ---------- Assets ----------

@router.get("/assets")
async def get_assets(
    type: str | None = None,
    status: str | None = None,
    location: str | None = None,
    employee_id: int | None = None,
    unassigned: bool = False,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await inv.list_assets(
        db, asset_type=type, status=status, location=location,
        employee_id=employee_id, unassigned=unassigned, q=q,
    )


@router.post("/assets", status_code=201)
async def post_asset(data: dict, db: AsyncSession = Depends(get_db)):
    if not data.get("asset_type"):
        raise HTTPException(400, "asset_type обязателен")
    asset = await inv.create_asset(db, data)
    return {"id": asset.id}


@router.put("/assets/{asset_id}")
async def put_asset(asset_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    asset = await inv.update_asset(db, asset_id, data)
    if not asset:
        raise HTTPException(404, "Техника не найдена")
    return {"id": asset.id}


@router.delete("/assets/{asset_id}", status_code=204)
async def del_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    ok = await inv.delete_asset(db, asset_id)
    if not ok:
        raise HTTPException(404, "Техника не найдена")


@router.post("/assets/{asset_id}/assign/{employee_id}")
async def assign(asset_id: int, employee_id: int, db: AsyncSession = Depends(get_db)):
    asset = await inv.assign_asset(db, asset_id, employee_id)
    if not asset:
        raise HTTPException(404, "Не найдено")
    return {"ok": True}


@router.post("/assets/{asset_id}/unassign")
async def unassign(asset_id: int, db: AsyncSession = Depends(get_db)):
    asset = await inv.assign_asset(db, asset_id, None)
    if not asset:
        raise HTTPException(404, "Не найдено")
    return {"ok": True}


@router.get("/meta")
async def get_meta():
    return {"types": inv.ASSET_TYPES, "statuses": inv.ASSET_STATUSES}


# ---------- Import ----------

@router.post("/inventory/import")
async def import_inventory(data: dict, db: AsyncSession = Depends(get_db)):
    text = data.get("text", "")
    default_type = data.get("default_type", "Прочее")
    if not text.strip():
        raise HTTPException(400, "Пустой текст")
    result = await inv.import_assets(db, text, default_type)
    return result
