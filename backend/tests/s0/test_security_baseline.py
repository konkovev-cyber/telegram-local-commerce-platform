import re
import pytest
from pydantic import ValidationError
from app.core.security import get_password_hash, verify_password
from app.modules.auth.jwt import create_access_token, decode_access_token
from app.modules.shops.crypto import encrypt_bot_token, decrypt_bot_token
from app.core.config import Settings

TELEGRAM_TOKEN_PATTERN = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")


def test_password_hashing():
    raw_password = "supersecretpassword123"
    hashed = get_password_hash(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_token_encode_decode():
    payload = {"sub": "123e4567-e89b-12d3-a456-426614174000", "role": "owner"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["role"] == payload["role"]
    assert "exp" in decoded


def test_bot_token_encryption_and_decryption_cycle():
    raw_bot_token = "1234567890:" + "A" * 35
    assert TELEGRAM_TOKEN_PATTERN.match(raw_bot_token)

    # 1. Plaintext != Encrypted
    encrypted = encrypt_bot_token(raw_bot_token)
    assert encrypted != raw_bot_token

    # 2. Encrypted does not match plaintext format
    assert not TELEGRAM_TOKEN_PATTERN.match(encrypted)

    # 3. Decrypt(Encrypt(x)) == x
    decrypted = decrypt_bot_token(encrypted)
    assert decrypted == raw_bot_token


def test_application_refuses_to_start_without_encryption_key():
    # Проверяем, что при пустом или невалидном ключе приложение не генерирует
    # новый ключ на лету, а падает с ValidationError при старте
    with pytest.raises(ValidationError):
        Settings(token_encryption_key="")

    with pytest.raises(ValidationError):
        Settings(token_encryption_key="invalid-non-base64-key")
