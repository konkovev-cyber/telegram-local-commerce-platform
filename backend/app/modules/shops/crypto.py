from cryptography.fernet import Fernet
from app.core.config import settings


def encrypt_bot_token(plaintext: str) -> str:
    """
    INV-009: шифрует токен бота симметричным ключом Fernet.
    Plaintext НИКОГДА не сохраняется в БД и не логируется.
    """
    f = Fernet(settings.token_encryption_key.encode())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_bot_token(encrypted: str) -> str:
    f = Fernet(settings.token_encryption_key.encode())
    return f.decrypt(encrypted.encode()).decode()
