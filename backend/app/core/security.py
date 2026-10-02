import bcrypt


def get_password_hash(password: str) -> str:
    """
    Хэширование пароля с солью с использованием прямого bcrypt.
    Исключает баги устаревшего passlib с версиями bcrypt 4.x/5.x.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка совпадения пароля.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False
