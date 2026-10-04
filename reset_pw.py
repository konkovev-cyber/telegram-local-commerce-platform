import asyncio, bcrypt
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def reset():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode()
            user = User(username='admin', hashed_password=hashed)
            db.add(user)
        else:
            hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode()
            user.hashed_password = hashed
        await db.commit()
        print('Password reset')

asyncio.run(reset())
