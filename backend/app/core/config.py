import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_commerce"
    database_pool_size: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "development-secret-key-change-in-production-min-32-chars-long"
    token_encryption_key: str = "dGhpcy1pcy1hLTMyLWJ5dGUtZmVybmV0LWtleS1leGFtcGxlPQ=="  # 32 bytes base64 urlsafe
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Telegram Platform Bot
    platform_bot_token: str = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"
    telegram_bot_secret: str = "test-bot-secret"

    # Runtime
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
