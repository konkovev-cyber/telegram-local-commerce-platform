from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/database.db"
    secret_key: str = "change-me-in-production"
    allowed_hosts: List[str] = ["localhost", "127.0.0.1"]
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    seed_data: bool = True
    data_dir: str = "./data"
    attachments_dir: str = "./data/attachments"
    backups_dir: str = "./data/backups"
    max_attachment_size: int = 10 * 1024 * 1024  # 10MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
