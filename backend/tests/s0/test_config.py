import pytest
from app.core.config import settings


def test_settings_loaded():
    assert settings.secret_key is not None
    assert len(settings.secret_key) >= 32
    assert settings.jwt_algorithm == "HS256"
    assert settings.token_encryption_key is not None
    assert settings.database_url is not None
    assert settings.redis_url is not None
