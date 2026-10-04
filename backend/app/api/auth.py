from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import auth as auth_services
from app.models import User
from sqlalchemy import select
import os

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_user_or_default(db: AsyncSession):
    default_user = db.execute(select(User).limit(1)).scalar_one_or_none()
    if not default_user:
        default_user = User(username="admin", hashed_password=auth_services.hash_password("admin"))
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
    return default_user


@router.post("/login")
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


@router.post("/change-password")
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
