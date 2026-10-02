import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    shop_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    actor_type: str = "user",
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    INV-011: вызывать ВНУТРИ транзакции основной операции.
    НЕ делать commit здесь!
    """
    log_entry = AuditLog(
        shop_id=shop_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(log_entry)
    return log_entry
