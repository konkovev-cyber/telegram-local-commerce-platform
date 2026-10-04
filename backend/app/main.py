from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, init_db, AsyncSessionLocal
from app.config import settings
from app.models import User
from app.services import auth as auth_services
from sqlalchemy import select
import os

# Create data directories
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.attachments_dir, exist_ok=True)
os.makedirs(settings.backups_dir, exist_ok=True)

app = FastAPI(
    title="SysVault",
    description="Local knowledge base for system administrators",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    if settings.seed_data:
        async with AsyncSessionLocal() as db:
            from app.services.entries import seed_categories, seed_entries
            await seed_categories(db)
            await seed_entries(db)


def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]
    payload = auth_services.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/auth/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not auth_services.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_services.create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/change-password")
async def change_password(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Passwords required")

    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not auth_services.verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid current password")

    user.hashed_password = auth_services.hash_password(new_password)
    await db.commit()
    return {"message": "Password changed"}


from app.api import entries, categories, attachments, backup, inventory

app.include_router(entries.router)
app.include_router(categories.router)
app.include_router(attachments.router)
app.include_router(backup.router)
app.include_router(inventory.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
