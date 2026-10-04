from app.main import app
from app.database import Base, engine, init_db
from app.services.entries import seed_categories, seed_entries
from app.models import User
from app.services.auth import hash_password

import asyncio
import os

os.makedirs("./data", exist_ok=True)

async def main():
    await init_db()
    await seed_categories(None if False else type('db', (), {'execute': lambda s, q: None})())
    print("DB initialized")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
