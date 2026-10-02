import os
from pydantic import field_validator
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
    token_encryption_key: str = "vog7CBI3kEVUdhdebHkK0RSKrRb7D3ldhzFup8DBaQ4="  # 32 bytes base64 urlsafe
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @field_validator("token_encryption_key")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("TOKEN_ENCRYPTION_KEY cannot be empty. Application refuses to start.")
        try:
            # Проверяем, что ключ валиден для Fernet
            from cryptography.fernet import Fernet
            Fernet(v.encode())
        except Exception as e:
            raise ValueError(f"Invalid TOKEN_ENCRYPTION_KEY for Fernet encryption: {e}")
        return v


    # Telegram Platform Bot
    platform_bot_token: str = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"
    telegram_bot_secret: str = "test-bot-secret"

    # Runtime
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
