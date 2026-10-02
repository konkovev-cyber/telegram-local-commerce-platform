# ADR-000: Architecture Freeze v1 Baseline

- **Date:** 2026-10-02
- **Status:** Accepted
- **Author:** System Architect & Platform Lead

## Context
Система создаётся как мультитенантная платформа локальной торговли в Telegram (Local Commerce Platform).
Для исключения рисков критических переделок при масштабировании утверждены фундаментальные инварианты (INV-001 - INV-012), исключены преждевременные технологии (Kubernetes, AI, pgvector) и зафиксированы границы MVP (S0-S3 core engine).

## Decision
1. Единый источник архитектурной правды зафиксирован в:
   - `docs/architecture_freeze_v1.md`
   - `docs/invariants_contract.md`
   - `docs/master_prompt_s0_s3.md`
2. Любое изменение в файлах контрактов блокируется CI без наличия утверждённого документа `docs/adr/ADR-XXXX.md`.
3. Установлены 12 обязательных инвариантов, валидируемых pytest на реальном PostgreSQL без моков.

## Consequences
- Разработка строго следует спринтам S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7.
- Запрещено добавление любых колонок/полей, нарушающих изоляцию тенантов и бухгалтерский учет остатков.
