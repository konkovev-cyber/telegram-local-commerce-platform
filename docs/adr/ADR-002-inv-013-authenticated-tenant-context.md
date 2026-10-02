# ADR-002: Introduction of INV-013 Authenticated Tenant Context Invariant

- **Date:** 2026-10-02
- **Status:** Accepted
- **Author:** System Architect & Platform Lead

## Context
В ходе аудита S0 было выявлено, что заголовок `X-Shop-Id` может быть ошибочно воспринят как определяющий tenant для авторизованного пользователя. Сам по себе заголовок или URL-параметр не должен предоставлять доступ к данным магазина. Доступ должен строго определяться подтверждённым членством пользователя в `shop_members`.

## Decision
Добавлен архитектурный инвариант **INV-013**:
1. Tenant context MUST be derived from authenticated identity and verified shop membership.
2. Client-provided `shop_id`, `X-Shop-Id` header, query/path parameters MUST NEVER grant tenant access without verified membership in `shop_members`.
3. Матрица изоляции ресурсов проверяет не только GET списков, но и мутации (POST, PATCH, DELETE) и вложенные ресурсы (`/orders/{id}/items`, `/products/{id}`, `/waves/{id}`).

## Old Behavior
Контекст проверялся только валидацией заголовка на уровне некоторых хэндлеров без явного инвариантного теста на nested-ресурсы и попытки мутаций.

## Invariants Affected
- Добавлен `INV-013` в `docs/invariants_contract.md`
- Добавлен тест `backend/tests/invariants/test_inv_013_tenant_context_authenticated_membership.py`

## Impact
- Полностью исключены риски IDOR на корневых и вложенных ресурсах.
- Сервер всегда самостоятельно валидирует `user ∈ shop_members(shop_id)`.

## Approved By
Platform Lead & Security Officer
