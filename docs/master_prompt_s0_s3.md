# Master Prompt: S0 → S3
## Telegram Local Commerce Platform
### Production-Grade Backend Contract for AI Developer

> **Это не задание "сделай backend".**  
> Это контракт, по которому ты строишь систему и сам себя проверяешь после каждого этапа.  
> Архитектура зафиксирована. Ты реализуешь её — не проектируешь заново.

---

## ЧАСТЬ 0: Правила и запреты

### Что ты ОБЯЗАН делать

1. **Следовать Architecture Freeze v1** — он является source of truth
2. **Писать тесты до или вместе с кодом** — не после
3. **Запускать invariant tests после каждого спринта** — все должны быть зелёными
4. **Сохранять ADR** при любом отклонении от архитектуры
5. **Докладывать результат** по шаблону Definition of Done после каждого спринта

### Что тебе ЗАПРЕЩЕНО
 
| Запрет | Причина |
|--------|---------|
| Изменять, ослаблять, скипать (`skip`/`xfail`) тесты в `tests/invariants/` | **Invariant tests are SPECIFICATION, not implementation tests.** Failures must be fixed in code! |
| Мокать поведение БД в тестах инвариантов | Тесты должны проверять реальные блокировки, триггеры и транзакции PostgreSQL |
| Добавлять `stock_qty` в `products` или `variants` | INV-001 |
| Хранить `paid`/`unpaid` в `orders.order_status` | INV-006 |
| Писать `bot_token` в `shops` как TEXT | INV-009 |
| Изменять `order_items.unit_price` после создания | INV-005 |
| Прямой UPDATE `inventory_items.available_qty` без movement | INV-003 |
| Обрабатывать webhook без сохранения raw event и проверки повторного бизнес-эффекта | INV-007 |
| Коммитить order без outbox_event в той же транзакции | INV-010 |
| Привилегированная мутация без audit_log | INV-011 |
| Возвращать данные чужого shop_id (включая прямой IDOR) | INV-012 |
| Создавать Kubernetes / Helm | Не нужно до нагрузки |
| Интегрировать AI / pgvector / embeddings | Не в MVP |

### Правило неприкосновенности спецификации (Invariant Rule)

```text
Invariant tests are specification, not implementation tests.

If implementation fails an invariant:
    fix implementation.

Do NOT:
    weaken assertion
    remove assertion
    reduce concurrency
    mock away the database behavior
    skip the test
    mark xfail
    change expected behavior

An invariant test may change only when:
    1. Architecture Freeze changes
    2. ADR is created
    3. The change is explicitly approved
    4. The corresponding test is updated
```

### ADR-формат (при отклонении от архитектуры)

```markdown
# ADR-NNN: [Название]
Date: YYYY-MM-DD  Status: Proposed
## Context / Decision / Consequences / Invariants affected
```

Сохранять в `docs/adr/ADR-NNN.md`.

---

## ЧАСТЬ 1: Стек

```
Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 (async/asyncpg)
Pydantic v2, Alembic, PostgreSQL 16, Redis 7
arq (async queue), cryptography (Fernet), python-jose
pytest + pytest-asyncio + httpx + factory-boy
```

### Структура модуля (обязательная)

```
app/modules/{domain}/
├── models.py       # SQLAlchemy ORM (ТОЛЬКО здесь)
├── schemas.py      # Pydantic schemas
├── service.py      # Business logic (ТОЛЬКО здесь, не в роутерах)
├── router.py       # FastAPI router (ТОЛЬКО валидация + вызов service)
├── exceptions.py   # Domain exceptions
└── dependencies.py # FastAPI Depends
```

---

## ЧАСТЬ 2: S0 — Инфраструктура

### Definition of Done S0

```
[ ] docker-compose.yml: postgres, redis, backend, worker, nginx
[ ] alembic upgrade head — без ошибок
[ ] GET /health → 200
[ ] GET /ready → 503 если postgres/redis недоступен
[ ] Логи в JSON: timestamp, level, logger, message, trace_id
[ ] .env.example со всеми переменными
[ ] Все секреты из env, ничего захардкожено
[ ] .gitignore исключает .env
[ ] GitHub Actions: тесты на push
[ ] pytest tests/ -x — проходит на чистой БД
```

### docker-compose.yml

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: telegram_commerce
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes: [postgres_data:/var/lib/postgresql/data]
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s  timeout: 5s  retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s  timeout: 3s  retries: 5

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/telegram_commerce
      REDIS_URL: redis://redis:6379/0
    ports: ["8000:8000"]
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}

  worker:
    build: ./backend
    command: python -m arq app.worker.main.WorkerSettings
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/telegram_commerce
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}

  nginx:
    image: nginx:alpine
    volumes: [./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro]
    ports: ["80:80"]
    depends_on: [backend]

volumes:
  postgres_data:
```

### Config

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    database_pool_size: int = 10
    redis_url: str
    secret_key: str           # JWT, min 32 chars
    token_encryption_key: str # Fernet key — для bot tokens
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    platform_bot_token: str
    telegram_bot_secret: str
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

settings = Settings()
```

### Health endpoints

```python
# app/api/v1/health.py
@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/ready")
async def ready():
    checks = {}
    try:
        async with AsyncSessionLocal() as s: await s.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e: checks["postgres"] = str(e)
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping(); await r.aclose()
        checks["redis"] = "ok"
    except Exception as e: checks["redis"] = str(e)
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503,
                       content={"status": "ready" if ok else "not_ready", "checks": checks})
```

### Logging (JSON)

```python
# app/core/logging.py
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname, "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(""),
            "module": record.module, "line": record.lineno,
        })
```

---

## ЧАСТЬ 3: S1 — Auth + Shops + Members

### Definition of Done S1

```
[ ] POST /api/v1/auth/telegram — HMAC валидация initData → JWT
[ ] initDataUnsafe НИКОГДА не принимается без валидации
[ ] JWT: sub (user_id), shop_id, role
[ ] POST /api/v1/admin/shops — создать магазин
[ ] POST /api/v1/admin/shops/{id}/members — добавить участника
[ ] POST /api/v1/admin/shops/{id}/bot — сохранить зашифрованный токен
[ ] bot_token НИКОГДА не возвращается в API response
[ ] X-Shop-Id обязателен для /admin/* — проверка membership
[ ] Аудит пишется для всех привилегированных действий
[ ] pytest tests/invariants/test_inv_009* ✅
[ ] pytest tests/invariants/test_inv_012* ✅
[ ] pytest tests/s1/ ✅
```

### Telegram initData Validation (КРИТИЧНО)

```python
# app/modules/auth/telegram.py

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

    if time.time() - int(parsed.get("auth_date", 0)) > 3600:
        raise TelegramInitDataError("initData expired")

    return json.loads(parsed.get("user", "{}"))
```

### Bot Token Encryption

```python
# app/modules/shops/crypto.py
def encrypt_bot_token(plaintext: str) -> str:
    # Plaintext НИКОГДА не логируется
    return Fernet(settings.token_encryption_key.encode()).encrypt(plaintext.encode()).decode()

def decrypt_bot_token(encrypted: str) -> str:
    return Fernet(settings.token_encryption_key.encode()).decrypt(encrypted.encode()).decode()
```

### RBAC Dependencies

```python
# app/modules/auth/dependencies.py

async def get_shop_context(
    x_shop_id: str = Header(..., alias="X-Shop-Id"),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
):
    """INV-012: фильтрует по shop_id из заголовка, не из токена."""
    shop, member = await ShopMemberService.get_shop_and_member(
        db, shop_id=x_shop_id, user_id=current_user.id)
    if not member:
        raise HTTPException(403, "Not a member of this shop")
    return shop, member

def require_shop_role(*roles: str):
    async def dep(shop_context=Depends(get_shop_context)):
        _, member = shop_context
        if member.shop_role not in roles:
            raise HTTPException(403, f"Required: {roles}")
        return shop_context
    return dep
```

### Negative Tests S1 (обязательны)

```python
# tests/s1/test_auth_negative.py
async def test_invalid_hmac_rejected(client):
    resp = await client.post("/api/v1/auth/telegram",
        json={"init_data": "hash=invalid_hash&user={}"})
    assert resp.status_code == 401

async def test_expired_init_data_rejected(client):
    # auth_date = 2 часа назад
    ...
    assert resp.status_code == 401

async def test_wrong_shop_id_forbidden(client, shop_a_token, shop_b):
    resp = await client.get("/api/v1/admin/orders",
        headers={"Authorization": f"Bearer {shop_a_token}",
                 "X-Shop-Id": str(shop_b.id)})
    assert resp.status_code == 403

async def test_bot_token_not_in_response(client, auth_headers):
    resp = await client.get("/api/v1/admin/shops/my", headers=auth_headers)
    assert "bot_token" not in resp.text
    assert "encrypted_token" not in resp.text
```

---

## ЧАСТЬ 4: S2 — Catalog + Pricing + Media

### Definition of Done S2

```
[ ] CRUD категорий (дерево, depth <= 3)
[ ] CRUD товаров: SKU, barcode, unit, cost_price
[ ] CRUD вариантов
[ ] Цены: только через prices-таблицу (history)
[ ] GET /catalog/products/{id} → текущая цена (valid_to IS NULL)
[ ] POST /admin/products/{id}/price → новая запись, старая закрывается (не удаляется)
[ ] Media: upload → S3/R2 → URL в product_media
[ ] CSV import: 3 шага (preview → validate → confirm)
[ ] CSV errors: построчно {row, field, message, severity}
[ ] order_items snapshot: product_name, variant_name, sku, unit, unit_price, cost_price
[ ] pytest tests/invariants/test_inv_001* ✅
[ ] pytest tests/invariants/test_inv_005* ✅
[ ] pytest tests/s2/ ✅
```

### Price History Service

```python
async def set_price(session, *, product_id, variant_id=None, amount, currency, created_by):
    """
    INV-005: существующие order_items НЕ затрагиваются.
    INV-011: пишет audit_log в той же транзакции.
    """
    now = datetime.now(timezone.utc)
    current = await _get_active_price(session, product_id, variant_id)
    if current:
        current.valid_to = now  # закрываем старую, НЕ удаляем
    new_price = Price(product_id=product_id, variant_id=variant_id,
                      amount=amount, currency=currency,
                      valid_from=now, valid_to=None, created_by=created_by)
    session.add(new_price)
    await write_audit(session, action="product.price_change", entity_id=product_id,
                      before={"amount": str(current.amount)} if current else None,
                      after={"amount": str(amount), "currency": currency},
                      actor_id=created_by)
    return new_price
```

### CSV Import: 3-step API

```
POST /api/v1/admin/products/import/preview     → {import_id, errors[], preview[]}
POST /api/v1/admin/products/import/{id}/confirm → {imported, skipped, job_id}
GET  /api/v1/admin/products/import/{id}/status  → {status, imported, errors[]}
```

---

## ЧАСТЬ 5: S3 — Inventory

### Definition of Done S3

```
[ ] inventory_items создаётся при создании product (stock_tracking=True)
[ ] InventoryService.initialize() создаёт item + movement типа 'purchase'
[ ] InventoryService.reserve() → SELECT FOR UPDATE → движение 'reservation'
[ ] InsufficientStockError если qty > available_qty
[ ] inventory_reservations имеют expires_at + status
[ ] arq task каждые 5 мин снимает просроченные резервации
[ ] InventoryService.sell() → movement 'sale' (reservation → sold)
[ ] InventoryService.release() → movement 'reservation_release'
[ ] InventoryService.correct() → movement 'correction' + audit_log
[ ] Нет прямых UPDATE inventory_items.available_qty без movement
[ ] pytest tests/invariants/ — ВСЕ 12 зелёные (включая INV-004)
[ ] pytest tests/s3/ ✅
```

### Inventory Service: reserve() — ключевой алгоритм

```python
async def reserve(session, *, inventory_id, qty, order_id, ttl_minutes=15):
    """
    INV-004: SELECT FOR UPDATE блокирует строку до конца транзакции.
    INV-003: создаёт movement в append-only ledger.
    Raises: InsufficientStockError
    """
    if qty <= 0:
        raise ValueError("qty must be positive")

    # КРИТИЧНО: FOR UPDATE
    item = (await session.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_id).with_for_update()
    )).scalar_one()

    if item.available_qty < qty:
        raise InsufficientStockError(
            f"Requested {qty}, available {item.available_qty}")

    before = item.available_qty
    item.available_qty -= qty
    item.reserved_qty += qty

    session.add(InventoryReservation(
        inventory_id=item.id, order_id=order_id, qty=qty,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        status="active",
    ))
    session.add(InventoryMovement(
        shop_id=item.shop_id, inventory_id=item.id,
        type="reservation", qty=-qty,
        before_available=before, after_available=item.available_qty,
        reference_type="order", reference_id=order_id,
    ))
```

### TTL Cleaner (arq)

```python
# app/worker/tasks/inventory.py
async def release_expired_reservations(ctx):
    """Каждые 5 минут. INV-003: через release(), не прямым UPDATE."""
    async with AsyncSessionLocal() as session:
        expired = (await session.execute(
            select(InventoryReservation).where(
                InventoryReservation.status == "active",
                InventoryReservation.expires_at < datetime.now(timezone.utc))
        )).scalars().all()
        for r in expired:
            try:
                await InventoryService.release(session, reservation_id=r.id)
            except Exception as e:
                logger.error(f"Failed to release {r.id}: {e}")
        await session.commit()

# app/worker/main.py
class WorkerSettings:
    redis_settings = settings.redis_url
    cron_jobs = [
        cron(release_expired_reservations,
             minute={0,5,10,15,20,25,30,35,40,45,50,55})
    ]
```

---

## ЧАСТЬ 6: Outbox Pattern

```python
# app/core/outbox.py
async def emit(session, *, shop_id, event_type, aggregate_type, aggregate_id, payload):
    """
    INV-010: вызывать ДО commit, внутри той же транзакции.

    # Пример в OrderService.create():
    session.add(order)
    await session.flush()          # получаем order.id
    await emit(session,            # ← в той же транзакции
        event_type="order.created",
        aggregate_id=order.id, ...)
    await session.commit()         # ← order + outbox вместе
    """
    session.add(OutboxEvent(
        shop_id=shop_id, event_type=event_type,
        aggregate_type=aggregate_type, aggregate_id=aggregate_id,
        payload=payload, status="pending",
    ))

# app/worker/tasks/outbox.py — worker с skip_locked для параллельности
async def process_outbox(ctx):
    async with AsyncSessionLocal() as session:
        events = (await session.execute(
            select(OutboxEvent).where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at).limit(50)
            .with_for_update(skip_locked=True)
        )).scalars().all()
        # → dispatch: Telegram / analytics / counters
```

---

## ЧАСТЬ 7: Idempotency Middleware

```python
# app/core/idempotency.py
# INV-008: POST /orders и POST /payments/create

PROTECTED_PATHS = {"/api/v1/orders", "/api/v1/payments/create"}

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path not in PROTECTED_PATHS: return await call_next(request)
        key = request.headers.get("Idempotency-Key")
        if not key: return await call_next(request)

        redis_key = f"idempotency:{request.url.path}:{key}"
        cached = await redis_client.get(redis_key)
        if cached:
            data = json.loads(cached)
            return Response(data["body"], status_code=data["status_code"],
                           headers={"X-Idempotent-Replay": "true"})
        response = await call_next(request)
        if response.status_code in (200, 201):
            # кешируем на 24ч
            ...
        return response
```

---

## ЧАСТЬ 8: Audit Helper

```python
# app/modules/audit/service.py
async def write_audit(session, *, shop_id=None, actor_id=None,
                      actor_type="user", action, entity_type,
                      entity_id, before=None, after=None, ip=None):
    """
    INV-011: вызывать ВНУТРИ транзакции основной операции.
    НЕ делать commit здесь.
    """
    session.add(AuditLog(shop_id=shop_id, actor_id=actor_id, actor_type=actor_type,
                         action=action, entity_type=entity_type, entity_id=entity_id,
                         before=before, after=after, ip=ip))
```

---

## ЧАСТЬ 9: Обязательные Negative Tests

### S1

```
test_invalid_hmac_rejected            → 401
test_expired_init_data_rejected       → 401
test_wrong_shop_id_forbidden          → 403
test_insufficient_role_forbidden      → 403
test_bot_token_not_in_response        → token не в JSON
```

### S2

```
test_price_zero_rejected              → 422
test_csv_invalid_prices_in_preview    → errors[]
test_csv_unknown_category_warning     → severity=warning
test_other_shop_product_not_found     → 404
```

### S3

```
test_reserve_more_than_available      → InsufficientStockError
test_reserve_negative_qty             → ValueError
test_release_nonexistent              → ReservationNotFoundError
test_concurrent_10_tasks_no_oversell  → INV-004
test_expired_reservations_released    → TTL cleaner
test_correction_creates_movement      → INV-003
test_correction_creates_audit         → INV-011
```

---

## ЧАСТЬ 10: CI

```yaml
# .github/workflows/ci.yml
jobs:
  invariants:
    name: Architecture Invariants (MUST PASS)
    # ... postgres:16, redis:7 services
    steps:
      - run: cd backend && alembic upgrade head
      - run: cd backend && pytest tests/invariants/ -v --tb=long
      # Если хоть один invariant красный — CI падает, PR не мержится

  tests:
    needs: invariants
    steps:
      - run: cd backend && pytest tests/ --ignore=tests/invariants -v --cov=app --cov-fail-under=75
```

---

## ЧАСТЬ 11: Definition of Done — шаблон отчёта AI

После каждого спринта AI предоставляет:

```markdown
## Sprint S{N} — Report

### Completed
- [x] Каждый пункт DoD

### Test Results
- Invariants: pytest tests/invariants/ → 12 passed, 0 failed
- Sprint tests: pytest tests/s{N}/ → N passed, 0 failed
- Coverage: N%

### Files created
- backend/app/modules/{domain}/models.py
- backend/app/modules/{domain}/service.py
- ...

### Alembic migrations
- {revision}_s{N}_{description}.py

### ADRs filed
- None (или ссылка)

### Known issues / deferred
- (если есть — с обоснованием)

### Verify commands
docker compose up -d && \
alembic upgrade head && \
pytest tests/invariants/ tests/s{N}/ -v
```

---

## ЧАСТЬ 12: Финальная самопроверка S0→S3

```bash
#!/bin/bash
# Всё должно быть зелёным перед передачей на review.

docker compose up -d && sleep 5

curl -f http://localhost:8000/health   && echo "✅ Health"
curl -f http://localhost:8000/ready    && echo "✅ Ready"

docker compose exec backend alembic upgrade head && echo "✅ Migrations"

docker compose exec backend pytest tests/invariants/ -v
# Expected: 12 passed, 0 failed

docker compose exec backend pytest tests/s0/ tests/s1/ tests/s2/ tests/s3/ -v

# Race condition (slow, отдельно)
docker compose exec backend pytest tests/invariants/test_inv_004_no_oversell.py -v -s

docker compose exec backend pytest tests/ --cov=app --cov-report=term-missing | tail -5
```
