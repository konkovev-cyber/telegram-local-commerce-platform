import re
import pytest
from sqlalchemy import text

TELEGRAM_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")


@pytest.mark.asyncio
async def test_inv_009_no_plaintext_tokens(db_session):
    result = await db_session.execute(
        text("SELECT id, encrypted_token FROM shop_bots")
    )
    violations = [str(r.id) for r in result.fetchall()
                  if TELEGRAM_TOKEN_RE.match(r.encrypted_token)]
    assert not violations, (
        f"INV-009 VIOLATION: {len(violations)} plaintext bot tokens in DB: {violations}"
    )


def test_inv_009_encrypt_token_is_not_identity():
    from app.modules.shops.service import ShopBotService
    raw = "1234567890:AAbbCCddEEffGGhhIIjjKKllMMnnOOppQQrr"
    encrypted = ShopBotService.encrypt_token(raw)
    assert encrypted != raw, "INV-009 VIOLATION: encrypt_token returned plaintext."
    assert not TELEGRAM_TOKEN_RE.match(encrypted), (
        "INV-009 VIOLATION: Encrypted token matches plaintext pattern."
    )
