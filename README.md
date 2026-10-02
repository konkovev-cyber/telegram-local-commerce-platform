# Telegram Local Commerce Platform

Мультитенантная платформа локальных продаж и совместных закупок в Telegram.

## Архитектура и контракты

Система спроектирована по строгим архитектурным контрактам:
- `docs/architecture_freeze_v1.md` — зафиксированная доменная модель и архитектура
- `docs/invariants_contract.md` — 12 исполняемых архитектурных инвариантов
- `docs/master_prompt_s0_s3.md` — контракт разработки S0→S3
- `docs/adr/` — журнал архитектурных решений (ADR)

## Быстрый старт (S0 Инфраструктура)

### 1. Переменные окружения
```bash
cp .env.example .env
```

### 2. Запуск контейнеров (PostgreSQL 16, Redis 7, Backend, Worker, Nginx)
```bash
docker compose up -d
```

### 3. Применение миграций Alembic
```bash
docker compose exec backend alembic upgrade head
```

### 4. Проверка жизнеспособности (Health probes)
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### 5. Запуск тестов
```bash
# Тесты спринта S0
docker compose exec backend pytest tests/s0/ -v

# Инварианты архитектуры
docker compose exec backend pytest tests/invariants/ -v
```
