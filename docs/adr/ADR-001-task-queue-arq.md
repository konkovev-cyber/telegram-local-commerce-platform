# ADR-001: Selection of ARQ over Celery for Async Background Queue

- **Date:** 2026-10-02
- **Status:** Accepted
- **Author:** System Architect & Platform Lead

## Context
Для выполнения фоновых задач (transactional outbox processing, очистка просроченных inventory reservations, отправка Telegram-уведомлений) требуется очередь задач с поддержкой Redis. В изначальных архитектурных обсуждениях упоминался Celery.

## Decision
Выбран **arq** (`arq>=0.26.0`) вместо **Celery** на стадии MVP (S0-S7):
1. **Async-native Python:** arq построен на `asyncio` и `redis-py` (async), что идеально интегрируется со стеком FastAPI + SQLAlchemy 2.0 (asyncpg).
2. **Отсутствие тяжелых зависимостей:** arq не тянет kombu, billiard, amqp и не требует запуска форков процессов с отдельными пулами соединений, в отличие от Celery.
3. **Единый Redis:** Redis 7 уже развернут в инфраструктуре для кэширования и идемпотентности, arq использует его напрямую.
4. **Легковесный cron:** встроенная поддержка cron-задач (запуск проверки резерваций каждые 5 минут, обработка outbox каждую минуту) без необходимости отдельного celery-beat контейнера.

## Old Behavior
Предполагалось использование Celery + Redis + Celery Beat с синхронными воркерами.

## Invariants Affected
- INV-010: Outbox worker (`app/worker/tasks/outbox.py`) использует arq с `with_for_update(skip_locked=True)`.
- Ни один фундаментальный бизнес-инвариант не нарушен.

## Impact
- Снижено потребление памяти базового стека на 150-250MB.
- Исключена рассинхронизация async event loop и синхронного Celery task runner.

## Approved By
Platform Lead & Security Officer
