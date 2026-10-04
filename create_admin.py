
import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from app.services.auth import hash_password
from sqlalchemy import select

async def create_user():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            user = User(username='admin', hashed_password=hash_password('admin'))
            db.add(user)
            await db.commit()
            print('Created admin user')
        else:
            print('Admin user exists')

asyncio.run(create_user())
