import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl


class TelegramInitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """
    КРИТИЧНО: использовать initData, НЕ initDataUnsafe.
    Ref: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramInitDataError("Missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise TelegramInitDataError("Invalid signature")

    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > 3600:
        raise TelegramInitDataError("initData expired")

    user_data = parsed.get("user")
    if not user_data:
        raise TelegramInitDataError("Missing user payload")

    return json.loads(user_data)
