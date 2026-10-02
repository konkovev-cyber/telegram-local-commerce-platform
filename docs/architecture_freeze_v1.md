# Architecture Freeze v1
## Telegram Local Commerce Platform

> **Принцип:** *Everything that happens to an order must be traceable, idempotent and auditable.*  
> Этот документ — финальная архитектура перед разработкой. Не менять без Architecture Decision Record.

---

## Оглавление

1. [Что изменилось относительно v0](#1-что-изменилось-относительно-v0)
2. [Стек](#2-стек)
3. [Архитектура системы](#3-архитектура-системы)
4. [Доменная модель](#4-доменная-модель)
5. [Полная схема БД](#5-полная-схема-бд)
6. [Машины состояний](#6-машины-состояний)
7. [Inventory — Ledger-модель](#7-inventory--ledger-модель)
8. [Payment — Abstraction Layer](#8-payment--abstraction-layer)
9. [Outbox Pattern](#9-outbox-pattern)
10. [Analytics Event Model](#10-analytics-event-model)
11. [Campaign Attribution](#11-campaign-attribution)
12. [Audit Log](#12-audit-log)
13. [API Endpoints](#13-api-endpoints)
14. [Telegram Integration](#14-telegram-integration)
15. [Структура репозитория](#15-структура-репозитория)
16. [MVP Business Loop](#16-mvp-business-loop)
17. [Что убрано из MVP](#17-что-убрано-из-mvp)
18. [Порядок разработки](#18-порядок-разработки)

---

## 1. Что изменилось относительно v0

| # | Проблема | v0 | v1 |
|---|---------|-----|-----|
| 1 | Inventory | `stock_qty` в products | Полноценный ledger: items + movements + reservations |
| 2 | Order state | Одно поле `status` смешивает всё | 3 независимые машины: order / fulfillment / payment |
| 3 | `paid` в order | Финансовое состояние в order | Убрано — только в payment |
| 4 | Payments | Одна таблица | payments + transactions + refunds + webhook_events |
| 5 | bot_token | `TEXT` в таблице shops | Отдельная `shop_bots`, токен зашифрован |
| 6 | Shared vs Own bot | Own bot для всех | MVP: shared bot + shop routing; Pro: own bot |
| 7 | Analytics | `campaign_events` на 4 типа | Универсальный `analytics_events` + session |
| 8 | Audit | Отсутствует | `audit_logs` со snapshot before/after |
| 9 | Idempotency | Отсутствует | `Idempotency-Key` на всех мутирующих endpoints |
| 10 | Webhook | Прямой `update order` | `webhook_events` → outbox → обработка |
| 11 | Price history | Нет | `prices` с `valid_from / valid_to` |
| 12 | Order snapshot | Частичный | Полный snapshot товара в момент заказа |
| 13 | cost_price | Нет | Добавлено в product/variant |
| 14 | shop_order_number | Глобальный IDENTITY | Scoped: UNIQUE(shop_id, number) |
| 15 | wave.number | Глобальный | UNIQUE(shop_id, number) |
| 16 | Assembly sheet | Без статусов | `pending → picking → packed → loaded` + qty tracking |
| 17 | SKU | Нет | Добавлено в product/variant |
| 18 | Customer identity | `telegram_id` в customers | `customers` + `customer_identities` |
| 19 | Currency | Только в payments | `shop.currency` → все денежные поля |
| 20 | Roles | Смешаны platform + shop | platform roles в `users`, shop roles в `shop_members` |
| 21 | Outbox | Нет | `outbox_events` в одной транзакции с order |
| 22 | Reservations | Нет | `inventory_reservations` с TTL |
| 23 | Route/Loading | Неверный термин | `pickup_manifest` + `loading_checklist` |
| 24 | AI | В MVP | Убрано полностью до v2 |
| 25 | pgvector | В MVP | Убрано полностью до v2 |
| 26 | Kubernetes | В MVP | Убрано. Docker Compose до появления нагрузки |
| 27 | Commission % | В монетизации | Только subscription. Marketplace split — v3 |

---

## 2. Стек

| Слой | Технология | Примечание |
|------|-----------|-----------|
| **Bot** | Aiogram 3 (Python) | Async, webhook mode |
| **Mini App** | React 18 + Vite + TypeScript | TG Web App SDK, TanStack Query, Zustand (только UI state) |
| **Admin** | React 18 + Vite + TypeScript | Тот же стек, переиспользование компонентов |
| **Backend** | FastAPI (Python 3.12) | Async, Pydantic v2, SQLAlchemy 2.0 (async) |
| **БД** | PostgreSQL 16 | Основное хранилище |
| **Cache** | Redis 7 | Сессии, idempotency keys, rate-limit |
| **Queue/Worker** | FastAPI + Redis + arq | Легче Celery для MVP; можно мигрировать |
| **Storage** | Cloudflare R2 / MinIO | Фото и видео товаров |
| **Secrets** | Vault / env encryption | Токены ботов, ключи провайдеров |
| **Payments** | Telegram Bot Payments → ЮKassa / Stripe | Provider abstraction layer |
| **Infra MVP** | Docker Compose | Только это до появления нагрузки |
| **CI/CD** | GitHub Actions | Build → test → deploy |

> **Убрано из MVP:** AI/GPT, pgvector, Celery, Kubernetes, own bot per shop.

---

## 3. Архитектура системы

```
TELEGRAM
    │
    ├── Customer ─────► [shared @PlatformBot]
    │                          │
    │         initData ────────┤
    │                          ▼
    │                   Mini App (SPA)
    │                   shop routing по slug / deep link
    │
    └── Seller ────────► Admin Panel (Web)
                                │
                    ┌───────────┴──────────────┐
                    │       FastAPI             │
                    │                          │
                    │  modules/                │
                    │  ├── auth                │
                    │  ├── shops               │
                    │  ├── catalog             │
                    │  ├── inventory           │
                    │  ├── customers           │
                    │  ├── waves               │
                    │  ├── orders              │
                    │  ├── fulfillment         │
                    │  ├── payments            │
                    │  ├── campaigns           │
                    │  ├── notifications       │
                    │  ├── analytics           │
                    │  └── audit               │
                    └────────┬─────────────────┘
                             │
              ┌──────────────┼───────────────┐
              ▼              ▼               ▼
         PostgreSQL        Redis         R2 / MinIO
              │
         outbox_events
              │
              ▼
           arq Worker
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
 Telegram  Analytics  Other
 Bot API   Events     Hooks
```

---

## 4. Доменная модель

```
SHOP
│
├── MEMBERS (platform roles + shop roles)
│
├── BOT (encrypted token, shared or own)
│
├── CATALOG
│   ├── CATEGORY (дерево)
│   ├── PRODUCT
│   │   ├── VARIANT
│   │   ├── PRICE (история цен, valid_from/valid_to)
│   │   └── MEDIA
│   └── UNIT
│
├── INVENTORY
│   ├── STOCK (current state: available / reserved / sold)
│   ├── RESERVATION (TTL, привязана к order)
│   └── MOVEMENT (ledger: purchase / reservation / release / sale / correction / refund)
│
├── CUSTOMERS
│   └── IDENTITY (provider: telegram, web, ...)
│
├── GEO
│   ├── ZONE
│   └── PICKUP_POINT
│
├── WAVES
│   ├── TIME_SLOT
│   ├── ASSEMBLY_SHEET (items с qty-статусами)
│   └── PICKUP_MANIFEST (loading checklist)
│
├── ORDERS
│   ├── ORDER_ITEMS (snapshot)
│   ├── ORDER_STATUS_LOG
│   ├── FULFILLMENT (отдельная машина состояний)
│   └── PAYMENT (отдельная машина состояний)
│       ├── PAYMENT_TRANSACTIONS
│       └── REFUNDS
│
├── CAMPAIGNS
│   ├── CAMPAIGN_SOURCES
│   └── ATTRIBUTION
│
├── ANALYTICS_EVENTS (universal event stream)
│
├── OUTBOX_EVENTS (transactional outbox)
│
└── AUDIT_LOGS
```

---

## 5. Полная схема БД

### 5.1 Platform: пользователи и магазины

```sql
-- Пользователи платформы
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(200) UNIQUE,
    hashed_password TEXT,
    platform_role   VARCHAR(30) NOT NULL DEFAULT 'user',
    -- platform_admin | support | user
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Магазины
CREATE TABLE shops (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(60) UNIQUE NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    logo_url    TEXT,
    currency    CHAR(3) NOT NULL DEFAULT 'RUB',
    owner_id    UUID NOT NULL REFERENCES users(id),
    plan        VARCHAR(20) NOT NULL DEFAULT 'free',
    -- free | start | business | pro
    plan_expires_at TIMESTAMPTZ,
    settings    JSONB NOT NULL DEFAULT '{}',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Роли внутри магазина
CREATE TABLE shop_members (
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shop_role   VARCHAR(30) NOT NULL DEFAULT 'operator',
    -- owner | manager | operator | picker | courier
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (shop_id, user_id)
);

-- Боты (зашифрованный токен, отдельно от shops)
-- MVP: один платформенный бот (shared), Pro: свой бот
CREATE TABLE shop_bots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    bot_username    VARCHAR(100) NOT NULL,
    bot_telegram_id BIGINT,
    encrypted_token TEXT NOT NULL,   -- application-level encryption, NOT plain text
    mode            VARCHAR(20) NOT NULL DEFAULT 'shared',
    -- shared | own
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shop_id)
);

-- Платёжные аккаунты магазина (провайдер + страна + credentials)
CREATE TABLE payment_accounts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    provider    VARCHAR(30) NOT NULL,
    -- telegram | yookassa | stripe | cash
    country     CHAR(2),
    currency    CHAR(3),
    credentials JSONB NOT NULL DEFAULT '{}', -- зашифровано
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.2 Каталог

```sql
-- Единицы измерения
CREATE TABLE units (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    name    VARCHAR(50) NOT NULL,   -- килограмм
    short   VARCHAR(20) NOT NULL    -- кг
);

-- Категории (дерево, depth <= 3 для MVP)
CREATE TABLE categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES categories(id),
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(200) NOT NULL,
    icon        TEXT,
    sort_order  INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    UNIQUE(shop_id, slug)
);

-- Товары
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    category_id     UUID REFERENCES categories(id),
    name            VARCHAR(300) NOT NULL,
    description     TEXT,
    sku             VARCHAR(100),
    barcode         VARCHAR(100),
    unit_id         UUID REFERENCES units(id),
    -- Себестоимость (для P&L)
    cost_price      NUMERIC(12,2),
    -- Тип ценообразования
    price_type      VARCHAR(20) NOT NULL DEFAULT 'per_unit',
    -- per_unit | per_kg | per_pack | tiered
    -- Управление остатками
    stock_tracking  BOOLEAN NOT NULL DEFAULT true,
    -- Тип наличия
    availability    VARCHAR(20) NOT NULL DEFAULT 'in_stock',
    -- in_stock | out_of_stock | preorder | hidden
    tags            TEXT[] NOT NULL DEFAULT '{}',
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shop_id, sku)
);

-- Варианты товара
CREATE TABLE product_variants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,  -- "1 кг", "Размер M / Синий"
    sku         VARCHAR(100),
    barcode     VARCHAR(100),
    qty_value   NUMERIC(12,3),          -- физическое кол-во для этого варианта
    cost_price  NUMERIC(12,2),
    sort_order  INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT true
);

-- История цен (для корректного snapshot и аналитики)
CREATE TABLE prices (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    product_id  UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id  UUID REFERENCES product_variants(id) ON DELETE CASCADE,
    amount      NUMERIC(12,2) NOT NULL,
    currency    CHAR(3) NOT NULL DEFAULT 'RUB',
    valid_from  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to    TIMESTAMPTZ,  -- NULL = текущая цена
    created_by  UUID REFERENCES users(id)
);
CREATE INDEX idx_prices_active ON prices(product_id, variant_id)
    WHERE valid_to IS NULL;

-- Ступенчатые цены (например: до 3 кг → 899, от 3 кг → 799)
CREATE TABLE price_tiers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price_id    UUID NOT NULL REFERENCES prices(id) ON DELETE CASCADE,
    min_qty     NUMERIC(12,3) NOT NULL,
    amount      NUMERIC(12,2) NOT NULL
);

-- Медиафайлы товара
CREATE TABLE product_media (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type        VARCHAR(10) NOT NULL CHECK (type IN ('image','video')),
    url         TEXT NOT NULL,
    sort_order  INT NOT NULL DEFAULT 0
);
```

### 5.3 Inventory (Ledger)

```sql
-- Текущее состояние остатка (денормализованный summary для скорости)
-- Источник истины — inventory_movements
CREATE TABLE inventory_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id      UUID REFERENCES product_variants(id) ON DELETE CASCADE,
    -- Текущий остаток (всегда = SUM движений)
    available_qty   NUMERIC(12,3) NOT NULL DEFAULT 0,
    reserved_qty    NUMERIC(12,3) NOT NULL DEFAULT 0,
    -- available_qty + reserved_qty = физический остаток
    sold_qty        NUMERIC(12,3) NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shop_id, product_id, variant_id)
);

-- Резервирование (TTL)
-- Создаётся при создании заказа, снимается при оплате/отмене/истечении
CREATE TABLE inventory_reservations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventory_id    UUID NOT NULL REFERENCES inventory_items(id),
    order_id        UUID NOT NULL,  -- FK добавляется позже из-за circular dep
    qty             NUMERIC(12,3) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,   -- TTL: +15 min (online) или wave.closes_at (cash)
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    -- active | confirmed | released | expired
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ledger движений (неизменяемый append-only журнал)
CREATE TABLE inventory_movements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID NOT NULL REFERENCES shops(id),
    inventory_id    UUID NOT NULL REFERENCES inventory_items(id),
    type            VARCHAR(30) NOT NULL,
    -- purchase      | входящая поставка
    -- reservation   | резервирование под заказ
    -- reservation_release | снятие резерва (отмена/истечение)
    -- sale          | фактическая продажа (выдача)
    -- correction    | ручная корректировка
    -- refund        | возврат
    qty             NUMERIC(12,3) NOT NULL,  -- + приход, - расход
    -- Что изменилось
    before_available NUMERIC(12,3) NOT NULL,
    after_available  NUMERIC(12,3) NOT NULL,
    -- Ссылка на источник движения
    reference_type  VARCHAR(30),   -- order | wave | manual
    reference_id    UUID,
    note            TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_inv_movements_inventory ON inventory_movements(inventory_id, created_at DESC);
```

### 5.4 Клиенты (CRM)

```sql
-- Клиент магазина (платформенная сущность, не Telegram-specific)
CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    display_name    VARCHAR(300),
    phone           VARCHAR(30),
    email           VARCHAR(200),
    preferred_zone_id UUID,  -- FK → zones
    -- CRM-агрегаты (кешируются, пересчитываются задачей)
    total_orders    INT NOT NULL DEFAULT 0,
    total_spent     NUMERIC(12,2) NOT NULL DEFAULT 0,
    avg_order_value NUMERIC(12,2) NOT NULL DEFAULT 0,
    last_order_at   TIMESTAMPTZ,
    top_products    UUID[] NOT NULL DEFAULT '{}',
    segments        TEXT[] NOT NULL DEFAULT '{}',
    -- loyal | vip | at_risk | new | churn
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Идентификаторы клиента (Telegram, web, WhatsApp, ...)
CREATE TABLE customer_identities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    provider    VARCHAR(30) NOT NULL,   -- telegram | web | whatsapp
    external_id VARCHAR(200) NOT NULL,  -- telegram_id, sub, phone
    username    VARCHAR(200),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, external_id)
);
```

### 5.5 География

```sql
CREATE TABLE zones (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(200) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    UNIQUE(shop_id, slug)
);

CREATE TABLE pickup_points (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id     UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    name        VARCHAR(300) NOT NULL,
    address     TEXT,
    lat         NUMERIC(10,7),
    lon         NUMERIC(10,7),
    maps_url    TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT true
);
```

### 5.6 Волны

```sql
CREATE TABLE waves (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    zone_id             UUID NOT NULL REFERENCES zones(id),
    pickup_point_id     UUID REFERENCES pickup_points(id),
    -- Номер волны в рамках магазина (не глобальный!)
    number              INT NOT NULL,
    name                VARCHAR(200),
    -- Приём заказов
    opens_at            TIMESTAMPTZ,
    closes_at           TIMESTAMPTZ NOT NULL,
    -- Выдача
    delivery_date       DATE NOT NULL,
    delivery_from       TIME NOT NULL,
    delivery_to         TIME NOT NULL,
    -- Ёмкость
    capacity_orders     INT,        -- максимум заказов
    min_orders          INT,        -- минимум для запуска
    -- Статус волны
    status              VARCHAR(30) NOT NULL DEFAULT 'collecting',
    -- collecting | closed | assembling | delivering | done | cancelled
    -- Агрегаты (пересчитываются триггером / задачей)
    orders_count        INT NOT NULL DEFAULT 0,
    items_count         INT NOT NULL DEFAULT 0,
    revenue_total       NUMERIC(12,2) NOT NULL DEFAULT 0,
    paid_online         NUMERIC(12,2) NOT NULL DEFAULT 0,
    paid_cash           NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shop_id, number)
);

CREATE TABLE wave_time_slots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wave_id     UUID NOT NULL REFERENCES waves(id) ON DELETE CASCADE,
    from_time   TIME NOT NULL,
    to_time     TIME NOT NULL,
    max_orders  INT
);

-- Лист сборки (агрегированный по волне)
CREATE TABLE assembly_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wave_id         UUID NOT NULL REFERENCES waves(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id),
    variant_id      UUID REFERENCES product_variants(id),
    -- Snapshot названий на момент генерации
    product_name    VARCHAR(300) NOT NULL,
    variant_name    VARCHAR(200),
    unit_short      VARCHAR(20),
    -- Количество
    required_qty    NUMERIC(12,3) NOT NULL,
    orders_count    INT NOT NULL,
    -- Статус сборки
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | picking | packed | loaded
    picked_qty      NUMERIC(12,3) NOT NULL DEFAULT 0,
    packed_qty      NUMERIC(12,3) NOT NULL DEFAULT 0,
    loaded_qty      NUMERIC(12,3) NOT NULL DEFAULT 0,
    -- Расхождения
    shortage_qty    NUMERIC(12,3) GENERATED ALWAYS AS
                        (required_qty - COALESCE(loaded_qty, 0)) STORED,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.7 Заказы (три независимые машины состояний)

```sql
-- Главная таблица заказа
CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    wave_id             UUID REFERENCES waves(id),
    customer_id         UUID NOT NULL REFERENCES customers(id),

    -- Номер заказа в рамках магазина (не глобальный!)
    number              BIGINT NOT NULL,

    -- ── MACHINE 1: Order lifecycle ──
    order_status        VARCHAR(30) NOT NULL DEFAULT 'new',
    -- new | confirmed | cancelled | completed | no_show

    -- Гео
    zone_id             UUID REFERENCES zones(id),
    pickup_point_id     UUID REFERENCES pickup_points(id),
    time_slot_id        UUID REFERENCES wave_time_slots(id),

    -- Финансы (snapshot на момент заказа)
    currency            CHAR(3) NOT NULL DEFAULT 'RUB',
    subtotal            NUMERIC(12,2) NOT NULL,
    discount_amount     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total               NUMERIC(12,2) NOT NULL,

    -- QR для выдачи
    qr_code             VARCHAR(100) UNIQUE,

    -- Attribution
    campaign_source_id  UUID,  -- FK → campaign_sources
    session_id          UUID,  -- FK → analytics_sessions

    -- Idempotency
    idempotency_key     VARCHAR(100) UNIQUE,

    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(shop_id, number)
);

-- Позиции заказа (полный snapshot на момент заказа)
CREATE TABLE order_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id      UUID REFERENCES products(id),       -- для аналитики
    variant_id      UUID REFERENCES product_variants(id),
    -- Snapshot (не менять при изменении каталога!)
    product_name    VARCHAR(300) NOT NULL,
    variant_name    VARCHAR(200),
    sku             VARCHAR(100),
    unit_short      VARCHAR(20),
    qty             NUMERIC(12,3) NOT NULL,
    unit_price      NUMERIC(12,2) NOT NULL,
    cost_price      NUMERIC(12,2),      -- snapshot себестоимости
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    subtotal        NUMERIC(12,2) NOT NULL
);

-- Лог изменений статуса заказа
CREATE TABLE order_status_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    field       VARCHAR(30) NOT NULL,   -- order_status | fulfillment_status | payment_status
    old_value   VARCHAR(30),
    new_value   VARCHAR(30) NOT NULL,
    changed_by  UUID REFERENCES users(id),
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── MACHINE 2: Fulfillment lifecycle ──
CREATE TABLE fulfillments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    status              VARCHAR(30) NOT NULL DEFAULT 'unfulfilled',
    -- unfulfilled | assembling | ready | out_for_delivery | arrived | delivered
    wave_id             UUID REFERENCES waves(id),
    delivery_date       DATE,
    delivered_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.8 Платежи (Ledger)

```sql
-- ── MACHINE 3: Payment lifecycle ──
CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id),
    shop_id             UUID NOT NULL REFERENCES shops(id),
    payment_account_id  UUID REFERENCES payment_accounts(id),

    method              VARCHAR(30) NOT NULL,
    -- cash | card_terminal | telegram | yookassa | stripe

    amount              NUMERIC(12,2) NOT NULL,
    currency            CHAR(3) NOT NULL DEFAULT 'RUB',

    status              VARCHAR(30) NOT NULL DEFAULT 'unpaid',
    -- unpaid | pending | paid | partially_paid | failed | refunded | partially_refunded

    -- Внешний ID провайдера
    provider_payment_id TEXT,
    -- Идемпотентность (защита от двойного платежа)
    idempotency_key     VARCHAR(100) UNIQUE,

    paid_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Транзакции платёжной системы (append-only)
CREATE TABLE payment_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id      UUID NOT NULL REFERENCES payments(id),
    type            VARCHAR(20) NOT NULL,
    -- charge | refund | chargeback | correction
    amount          NUMERIC(12,2) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'RUB',
    status          VARCHAR(20) NOT NULL,
    -- success | failed | pending
    provider_tx_id  TEXT,
    raw_response    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Возвраты
CREATE TABLE refunds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id      UUID NOT NULL REFERENCES payments(id),
    amount          NUMERIC(12,2) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'RUB',
    reason          TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | completed | failed
    provider_ref_id TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Сырые события от платёжных провайдеров (webhook ingestion)
CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID REFERENCES shops(id),
    provider        VARCHAR(30) NOT NULL,
    event_type      TEXT NOT NULL,
    provider_event_id TEXT,             -- для идемпотентности
    raw_body        JSONB NOT NULL,
    processed       BOOLEAN NOT NULL DEFAULT false,
    processed_at    TIMESTAMPTZ,
    error           TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, provider_event_id) -- дедупликация
);
```

### 5.9 Рекламные кампании и Attribution

```sql
CREATE TABLE campaigns (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    starts_at   TIMESTAMPTZ,
    ends_at     TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE campaign_sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    zone_id     UUID REFERENCES zones(id),
    name        VARCHAR(200) NOT NULL,    -- "Группа Солнечный район"
    ref_code    VARCHAR(100) NOT NULL,    -- solnechny_01
    deep_link   TEXT,
    -- Денормализованные счётчики (пересчитываются из analytics_events)
    clicks      INT NOT NULL DEFAULT 0,
    opens       INT NOT NULL DEFAULT 0,
    carts       INT NOT NULL DEFAULT 0,
    orders      INT NOT NULL DEFAULT 0,
    revenue     NUMERIC(12,2) NOT NULL DEFAULT 0,
    UNIQUE(ref_code)
);

-- Сессии для сквозной аналитики
CREATE TABLE analytics_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID REFERENCES shops(id),
    customer_id         UUID REFERENCES customers(id),
    campaign_source_id  UUID REFERENCES campaign_sources(id),
    -- Attribution
    utm_source          TEXT,
    utm_medium          TEXT,
    utm_campaign        TEXT,
    ref_code            TEXT,
    -- Device
    platform            VARCHAR(20),    -- android | ios | desktop
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.10 Analytics Events (Universal Stream)

```sql
CREATE TABLE analytics_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id             UUID NOT NULL REFERENCES shops(id),
    customer_id         UUID REFERENCES customers(id),
    session_id          UUID REFERENCES analytics_sessions(id),
    campaign_source_id  UUID REFERENCES campaign_sources(id),

    event_name          VARCHAR(60) NOT NULL,
    -- app_open | catalog_view | product_view | search
    -- add_to_cart | remove_from_cart
    -- checkout_started | checkout_completed
    -- order_created | order_cancelled | order_delivered
    -- payment_started | payment_completed | payment_failed
    -- campaign_click

    entity_type         VARCHAR(30),    -- product | order | wave | category
    entity_id           UUID,

    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Партиционирование по дате (при росте объёмов)
CREATE INDEX idx_analytics_events_shop_date ON analytics_events(shop_id, created_at DESC);
CREATE INDEX idx_analytics_events_name ON analytics_events(event_name, created_at DESC);
```

### 5.11 Outbox Events (Transactional Outbox Pattern)

```sql
-- Записывается в одной транзакции с бизнес-событием
-- Worker читает и доставляет: Telegram / analytics / webhooks / прочее
CREATE TABLE outbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         UUID REFERENCES shops(id),
    event_type      VARCHAR(60) NOT NULL,
    -- order.created | order.status_changed | payment.completed
    -- wave.closed | fulfillment.delivered | notification.send
    aggregate_type  VARCHAR(30) NOT NULL,    -- order | wave | payment
    aggregate_id    UUID NOT NULL,
    payload         JSONB NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | processing | done | failed
    attempts        INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX idx_outbox_pending ON outbox_events(status, created_at)
    WHERE status IN ('pending', 'failed');
```

### 5.12 Audit Log

```sql
CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID REFERENCES shops(id),
    actor_id    UUID REFERENCES users(id),
    actor_type  VARCHAR(20) NOT NULL DEFAULT 'user',
    -- user | system | webhook | bot
    action      VARCHAR(60) NOT NULL,
    -- order.cancel | product.price_change | payment.refund | stock.correction ...
    entity_type VARCHAR(30) NOT NULL,
    entity_id   UUID NOT NULL,
    before      JSONB,      -- состояние до
    after       JSONB,      -- состояние после
    ip          INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_shop ON audit_logs(shop_id, created_at DESC);
```

### 5.13 Промокоды (заложить, включить в v1.1)

```sql
CREATE TABLE promo_codes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    code        VARCHAR(50) NOT NULL,
    type        VARCHAR(20) NOT NULL,   -- percent | fixed
    value       NUMERIC(10,2) NOT NULL,
    min_order   NUMERIC(12,2) NOT NULL DEFAULT 0,
    max_uses    INT,
    used_count  INT NOT NULL DEFAULT 0,
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    UNIQUE(shop_id, code)
);
```

---

## 6. Машины состояний

### Order Lifecycle

```
new ──────────────────────────────► cancelled
 │
 ▼
confirmed ────────────────────────► cancelled
 │
 ▼
completed ◄──── (при fulfillment=delivered)
no_show   ◄──── (клиент не пришёл)
```

### Fulfillment Lifecycle

```
unfulfilled
    │  (wave.status → assembling)
    ▼
assembling
    │  (продавец собрал)
    ▼
ready
    │  (продавец выехал)
    ▼
out_for_delivery
    │  (приехал на точку)
    ▼
arrived
    │  (сканирует QR, нажимает ВЫДАТЬ)
    ▼
delivered ✅
```

### Payment Lifecycle

```
unpaid
  │  (cash on delivery → волна)
  ├──────────────────────────────► paid (при выдаче)
  │
  │  (online)
  ├── pending
  │      │
  │      ├── paid ✅
  │      ├── failed
  │      └── (retry)
  │
paid
  │
  ├── refunded (полный возврат)
  └── partially_refunded
```

### Wave Lifecycle

```
collecting  (принимаем заказы)
    │  (closes_at или ручное закрытие)
    ▼
closed  (заказы зафиксированы, генерируем assembly sheet)
    │
    ▼
assembling  (продавец собирает)
    │
    ▼
delivering  (продавец на точке)
    │
    ▼
done  (все заказы обработаны)

cancelled  (< min_orders к closes_at, или ручная отмена)
```

---

## 7. Inventory — Ledger-модель

### Инвариант

```
inventory_items.available_qty
    = SUM(movements.qty WHERE type IN ('purchase', 'reservation_release', 'refund'))
    - SUM(movements.qty WHERE type IN ('reservation', 'sale'))
```

### Сценарий: заказ с резервированием

```
Остаток свинины: 30 кг
Доступно: 30 кг
Зарезервировано: 0 кг

Клиент A создаёт заказ 10 кг:
  BEGIN TRANSACTION
    SELECT ... FOR UPDATE (inventory_items)
    INSERT inventory_reservations (qty=10, expires_at=NOW()+15min)
    INSERT inventory_movements (type=reservation, qty=-10)
    UPDATE inventory_items SET available_qty=20, reserved_qty=10
    INSERT outbox_events (order.created)
  COMMIT

Клиент B создаёт заказ 25 кг:
  BEGIN TRANSACTION
    SELECT ... FOR UPDATE
    CHECK: available_qty(20) < 25 → FAIL
    ROLLBACK → ответ: "недостаточно товара"

Клиент A оплатил:
  BEGIN TRANSACTION
    UPDATE inventory_reservations SET status=confirmed
    INSERT inventory_movements (type=sale, qty=-10)
    UPDATE inventory_items SET reserved_qty=0, sold_qty+=10
    UPDATE payments SET status=paid
    INSERT outbox_events (payment.completed)
  COMMIT

Клиент A отменил (до оплаты):
  BEGIN TRANSACTION
    UPDATE inventory_reservations SET status=released
    INSERT inventory_movements (type=reservation_release, qty=+10)
    UPDATE inventory_items SET available_qty=30, reserved_qty=0
    INSERT outbox_events (order.cancelled)
  COMMIT
```

---

## 8. Payment — Abstraction Layer

### Provider Interface

```python
class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment(
        self, order_id: UUID, amount: Money, idempotency_key: str
    ) -> PaymentIntent: ...

    @abstractmethod
    async def verify_webhook(
        self, raw_body: bytes, signature: str
    ) -> WebhookEvent: ...

    @abstractmethod
    async def refund(
        self, payment_id: str, amount: Money, reason: str
    ) -> RefundResult: ...

class TelegramPaymentProvider(PaymentProvider): ...
class YooKassaProvider(PaymentProvider): ...
class StripeProvider(PaymentProvider): ...
class CashProvider(PaymentProvider): ...   # Нет async операций; статус ставится вручную
```

### Webhook Pipeline

```
POST /payments/webhook/{provider}
    │
    ▼
1. verify signature (быстро, < 10ms)
    │
    ▼
2. INSERT webhook_events (raw_body, provider_event_id)
   UNIQUE constraint → защита от дублей
    │
    ▼
3. ответить 200 OK (Telegram требует < 10 сек)
    │
    ▼ (async, в worker)
4. process webhook_event
    │
    ▼
5. BEGIN TRANSACTION
   UPDATE payments
   INSERT payment_transactions
   UPDATE inventory (если нужно)
   UPDATE outbox_events
   COMMIT
    │
    ▼
6. outbox worker → уведомления
```

---

## 9. Outbox Pattern

```
Business operation (create order, confirm payment, close wave)
    │
    ▼
BEGIN TRANSACTION
  INSERT/UPDATE business entity
  INSERT outbox_events (pending)
COMMIT
    │
    ▼
arq Worker (polling outbox WHERE status=pending ORDER BY created_at)
    │
    ├── Telegram notification
    ├── analytics_events update
    ├── wave counters update
    └── campaign_sources counters update
```

**Гарантии:**
- Если Telegram упал → outbox остаётся pending, worker повторит
- Если worker упал → при рестарте возьмёт pending события
- Дублей не будет: `status=processing` + `attempts` counter

---

## 10. Analytics Event Model

### Event names (MVP)

| Event | Когда |
|-------|-------|
| `app_open` | Mini App открыт |
| `catalog_view` | Открыт каталог / категория |
| `product_view` | Открыта карточка товара |
| `search` | Поиск выполнен |
| `add_to_cart` | Товар добавлен в корзину |
| `remove_from_cart` | Товар удалён |
| `checkout_started` | Начато оформление |
| `checkout_completed` | Заказ подтверждён |
| `order_created` | Заказ создан (server-side) |
| `order_cancelled` | Отмена |
| `order_delivered` | Выдача подтверждена |
| `payment_started` | Запущена оплата |
| `payment_completed` | Оплата успешна |
| `payment_failed` | Оплата не прошла |
| `campaign_click` | Переход по рекламной ссылке |

### Воронка кампании (derived)

```sql
SELECT
    cs.name AS source,
    COUNT(*) FILTER (WHERE ae.event_name = 'campaign_click')  AS clicks,
    COUNT(*) FILTER (WHERE ae.event_name = 'app_open')         AS opens,
    COUNT(*) FILTER (WHERE ae.event_name = 'add_to_cart')      AS carts,
    COUNT(*) FILTER (WHERE ae.event_name = 'order_created')    AS orders,
    SUM(o.total) FILTER (WHERE ae.event_name = 'order_created') AS revenue
FROM analytics_events ae
JOIN campaign_sources cs ON ae.campaign_source_id = cs.id
LEFT JOIN orders o ON ae.entity_id = o.id
    AND ae.event_name = 'order_created'
WHERE ae.shop_id = $1
  AND ae.created_at >= $2
GROUP BY cs.id, cs.name;
```

---

## 11. Campaign Attribution

```
Deep link: t.me/platform_bot?start=ref_solnechny_01
    │
    ▼
Bot handler /start solnechny_01
    │
    ▼
Resolve campaign_source by ref_code
    │
    ▼
Create/update analytics_session (campaign_source_id, ref_code)
    │
    ▼
INSERT analytics_events (campaign_click, session_id)
    │
    ▼
Open Mini App с параметром ref_code в URL
    │
    ▼
Mini App → POST /auth/telegram с ref_code
    │
    ▼
Session привязана к customer_id
    │
    ▼
Все дальнейшие события session → автоматически атрибутированы к кампании
```

---

## 12. Audit Log

Каждое из этих действий **обязательно** пишет в `audit_logs`:

| Action | Trigger |
|--------|---------|
| `product.price_change` | Обновление `prices` |
| `stock.correction` | Ручная корректировка остатка |
| `order.cancel` | Отмена заказа |
| `payment.refund` | Возврат |
| `payment.manual_confirm` | Подтверждение оплаты вручную |
| `wave.close` | Закрытие волны |
| `fulfillment.deliver` | Выдача заказа |
| `shop.settings_change` | Изменение настроек магазина |

---

## 13. API Endpoints

### Покупатель (Mini App)

```
POST /api/v1/auth/telegram              # initData validation → JWT
GET  /api/v1/shops/{slug}               # Инфо о магазине
GET  /api/v1/shops/{slug}/catalog       # Категории + товары
GET  /api/v1/shops/{slug}/products/{id} # Карточка (с текущей ценой из prices)
GET  /api/v1/shops/{slug}/waves/active  # Активные волны
GET  /api/v1/waves/{id}/slots           # Слоты выдачи

POST /api/v1/cart/validate              # Проверка корзины (цены, остатки)
# Idempotency-Key required:
POST /api/v1/orders                     # Создать заказ + резервирование
GET  /api/v1/orders/{id}               # Заказ (с fulfillment и payment)
GET  /api/v1/orders/{id}/qr            # QR-код
GET  /api/v1/orders/my                 # История

POST /api/v1/payments/create            # Создать платёж (→ redirect или invoice)
POST /api/v1/payments/webhook/{provider} # Webhook
```

### Продавец (Admin)

```
# Dashboard
GET  /api/v1/admin/dashboard            # Сводка дня

# Волны
GET  /api/v1/admin/waves                # Список
POST /api/v1/admin/waves                # Создать волну
GET  /api/v1/admin/waves/{id}          # Детали волны
POST /api/v1/admin/waves/{id}/close    # Закрыть волну → assembly sheet
GET  /api/v1/admin/waves/{id}/assembly  # Лист сборки
PATCH /api/v1/admin/assembly/{item_id} # Обновить picked/packed/loaded qty
GET  /api/v1/admin/waves/{id}/manifest # Pickup manifest (загрузка авто)

# Заказы
GET  /api/v1/admin/orders              # Список (фильтр по статусу, волне, зоне)
GET  /api/v1/admin/orders/{id}         # Детали
PATCH /api/v1/admin/orders/{id}/order-status
PATCH /api/v1/admin/orders/{id}/fulfillment-status
POST /api/v1/admin/orders/{id}/deliver  # Выдать + принять оплату наличными
POST /api/v1/admin/qr/scan             # Scan QR → заказ
POST /api/v1/admin/orders/{id}/cancel  # Отмена + release резерва

# CRM
GET  /api/v1/admin/customers           # Список
GET  /api/v1/admin/customers/{id}      # Профиль + история

# Каталог
GET  /api/v1/admin/products            # Список
POST /api/v1/admin/products            # Создать
PATCH /api/v1/admin/products/{id}      # Обновить
POST /api/v1/admin/products/{id}/price # Новая цена (создаёт price record)
POST /api/v1/admin/products/import     # CSV import (preview → validate → confirm)
PATCH /api/v1/admin/inventory/{id}     # Ручная корректировка остатка

# Кампании
GET  /api/v1/admin/campaigns           # Список
POST /api/v1/admin/campaigns           # Создать
POST /api/v1/admin/campaigns/{id}/sources  # Добавить источник
GET  /api/v1/admin/campaigns/{id}/funnel   # Воронка конверсий

# Аналитика
GET  /api/v1/admin/analytics/sales     # Выручка + P&L
GET  /api/v1/admin/analytics/products  # ТОП товаров
GET  /api/v1/admin/analytics/zones     # По районам

# Настройки
GET  /api/v1/admin/settings
PATCH /api/v1/admin/settings
```

---

## 14. Telegram Integration

### Mini App Auth (обязательно server-side validation)

```python
import hashlib, hmac, time
from urllib.parse import parse_qsl

def validate_init_data(init_data: str, bot_token: str) -> dict:
    parsed = dict(parse_qsl(init_data))
    received_hash = parsed.pop("hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise ValueError("Invalid initData signature")

    # Проверяем свежесть (не старше 1 часа)
    if time.time() - int(parsed["auth_date"]) > 3600:
        raise ValueError("initData expired")

    return parsed   # user, auth_date, etc.
    # НИКОГДА не принимать initDataUnsafe без этой проверки!
```

### Deep Link сценарии

| Deep link | Действие |
|-----------|---------|
| `?start=ref_{code}` | Фиксируем attribution → открываем Mini App |
| `?start=order_{id}` | Открываем конкретный заказ в Mini App |
| `?start=wave_{id}` | Продавцу: экран волны в Admin |

### Уведомления (отправляются через outbox worker)

| Событие | Получатель | Текст |
|---------|-----------|-------|
| order.created | Продавец | 🛒 Новый заказ №{N} — {total} ₽ |
| order.created | Покупатель | ✅ Заказ №{N} принят. Выдача: {дата}, {адрес} |
| wave.closes_soon | Покупатель (без заказа в зоне) | ⏰ Последний шанс заказать до {time} |
| wave.closed | Покупатель (с заказом) | 🔒 Приём завершён. Ждём вас! |
| fulfillment.out_for_delivery | Покупатель | 🚗 Едем! Будем на точке в {time}. QR в приложении |
| fulfillment.arrived | Покупатель | 📍 Мы на месте! Покажите QR-код |
| fulfillment.delivered | Покупатель | 🎉 Заказ получен. Спасибо! |
| payment.completed | Покупатель | 💳 Оплата прошла: {amount} ₽ |

---

## 15. Структура репозитория

```
telegram-local-commerce/
│
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   │   ├── auth/            # JWT, initData validation
│   │   │   ├── shops/           # Магазины, участники, боты
│   │   │   ├── catalog/         # Категории, товары, цены, медиа
│   │   │   ├── inventory/       # Items, movements, reservations
│   │   │   ├── customers/       # CRM, identities
│   │   │   ├── geo/             # Zones, pickup points
│   │   │   ├── waves/           # Волны, слоты, assembly, manifest
│   │   │   ├── orders/          # Orders, items, status log
│   │   │   ├── fulfillment/     # Fulfillment state machine
│   │   │   ├── payments/        # Payments, transactions, refunds, webhooks
│   │   │   ├── campaigns/       # Campaigns, sources, attribution
│   │   │   ├── notifications/   # Templates + delivery (outbox consumer)
│   │   │   ├── analytics/       # Events, sessions, reporting
│   │   │   └── audit/           # Audit log
│   │   │
│   │   ├── core/
│   │   │   ├── db.py            # AsyncSession, get_db
│   │   │   ├── config.py        # Settings (pydantic-settings)
│   │   │   ├── security.py      # JWT, token encryption
│   │   │   ├── idempotency.py   # Idempotency-Key middleware
│   │   │   ├── outbox.py        # Outbox writer helper
│   │   │   └── money.py         # Money type (amount + currency)
│   │   │
│   │   ├── worker/
│   │   │   ├── outbox_processor.py  # arq worker: outbox → dispatch
│   │   │   ├── notification_sender.py
│   │   │   ├── reservation_cleaner.py   # TTL expired reservations
│   │   │   └── wave_auto_close.py
│   │   │
│   │   └── main.py
│   │
│   ├── alembic/
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── Dockerfile
│
├── bot/                         # Aiogram 3
│   ├── handlers/
│   │   ├── start.py             # Deep link routing
│   │   └── payments.py          # Pre-checkout, successful payment
│   ├── middlewares/
│   └── Dockerfile
│
├── miniapp/                     # React (покупатель)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Catalog.tsx
│   │   │   ├── Product.tsx
│   │   │   ├── Cart.tsx
│   │   │   ├── Checkout.tsx
│   │   │   ├── Order.tsx
│   │   │   └── Orders.tsx
│   │   ├── components/
│   │   ├── api/                 # TanStack Query hooks
│   │   ├── store/               # Zustand: cart + UI only
│   │   └── telegram/            # WebApp SDK hooks
│   └── Dockerfile
│
├── admin/                       # React (продавец)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Waves/
│   │   │   ├── Orders/
│   │   │   ├── Customers/
│   │   │   ├── Catalog/
│   │   │   ├── Campaigns/
│   │   │   ├── Analytics/
│   │   │   └── Settings/
│   │   ├── components/
│   │   └── api/
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml       # Единственная infra для MVP
│   ├── nginx/
│   │   └── nginx.conf
│   └── .env.example
│
└── scripts/
    ├── create_shop.py           # CLI: создать магазин
    ├── generate_deep_links.py
    └── seed_demo_catalog.py
```

---

## 16. MVP Business Loop

Единственная цель MVP: **этот цикл должен работать железно.**

```
1.  Продавец: создать магазин (admin)
         ↓
2.  Продавец: добавить товары с ценами и остатками
         ↓
3.  Продавец: создать зону и точку выдачи
         ↓
4.  Продавец: создать волну (дата, закрытие, слоты)
         ↓
5.  Продавец: получить рекламную ссылку для зоны
         ↓
6.  Покупатель: открыл ссылку → attribution зафиксирован
         ↓
7.  Покупатель: Mini App открыт → initData validated
         ↓
8.  Покупатель: выбрал товары, добавил в корзину
         ↓
9.  Покупатель: оформил заказ (зона / точка / слот / оплата)
         ↓
10. Система: зарезервировала остаток (SELECT FOR UPDATE)
         ↓
11. Система: создала order + fulfillment + payment в одной транзакции
         ↓
12. Система: вставила outbox_events
         ↓
13. Worker: отправил уведомления (покупатель + продавец)
         ↓
14. [Если онлайн-оплата]: Telegram invoice → ЮKassa/Stripe → webhook
         ↓
15. Продавец: закрыл волну → assembly sheet сгенерирован
         ↓
16. Продавец: проверил picked/packed/loaded qty в сборочном листе
         ↓
17. Продавец: нажал "Выехал" → уведомления покупателям
         ↓
18. Продавец: нажал "Приехали на точку" → уведомления
         ↓
19. Покупатель: подошёл → показал QR
         ↓
20. Продавец: сканировал QR → открылся заказ мгновенно
         ↓
21. Продавец: нажал ВЫДАТЬ + ввёл наличные → сдача
         ↓
22. Система: fulfillment=delivered, payment=paid, outbox event
         ↓
23. Worker: уведомление покупателю "Получен"
         ↓
24. Продавец: закрыл день → видит выручку + P&L + воронку рекламы
```

---

## 17. Что убрано из MVP

| Функция | Статус | Когда |
|---------|--------|-------|
| AI поиск товаров | ❌ MVP | v2 |
| AI прогноз закупки | ❌ MVP | v2 |
| AI ассистент продавца | ❌ MVP | v2 |
| pgvector | ❌ MVP | v2 |
| Повторный заказ (AI-триггер) | ❌ MVP | v2 |
| Промокоды | ❌ MVP | v1.1 |
| Наборы (bundling) | ❌ MVP | v1.1 |
| Реферальная программа | ❌ MVP | v2 |
| Сегментированные рассылки | ❌ MVP | v2 |
| Собственный бот на каждый магазин | ❌ MVP | Pro |
| Доставка по адресам (route) | ❌ MVP | v2 |
| Marketplace payment split | ❌ MVP | v3 |
| Kubernetes | ❌ MVP | при нагрузке |
| WhatsApp / web identity | ❌ MVP | v2 |

---

## 18. Порядок разработки (спринты)

| Спринт | Домен | Deliverable |
|--------|-------|-------------|
| **S0** (3 дня) | Infra | Docker Compose: PG + Redis + nginx. Alembic migrations. CI/CD pipeline |
| **S1** (1 нед) | Auth + Shops | POST /auth/telegram (initData validation). Shop CRUD. Shop members |
| **S2** (1 нед) | Catalog | Categories + Products + Variants + Prices (history). Media upload. CSV import |
| **S3** (1 нед) | Inventory | inventory_items + movements + reservations. SELECT FOR UPDATE. TTL cleaner |
| **S4** (1 нед) | Geo + Waves | Zones + Pickup points. Wave CRUD. Time slots. Wave lifecycle |
| **S5** (1.5 нед) | Orders | Order create (+ reserve inventory). 3 state machines. QR generation. Status transitions |
| **S6** (1 нед) | Payments | Cash flow. Telegram Payments + ЮKassa. Webhook ingestion pipeline. Refunds |
| **S7** (1 нед) | Fulfillment | Assembly sheet (с qty tracking). Pickup manifest. QR scan → deliver |
| **S8** (1 нед) | Notifications | Outbox worker. Telegram bot messages. Все события из таблицы выше |
| **S9** (1 нед) | Campaigns | Campaign + Sources + Deep links. Analytics sessions. Event stream. Воронка |
| **S10** (1 нед) | Admin UI | Все экраны Admin: волны, заказы, сборка, клиенты, кампании, аналитика P&L |
| **S11** (1 нед) | Mini App | Все экраны: каталог, корзина, checkout, заказ, QR, история |
| **S12** (1 нед) | QA + Polish | E2E business loop. Load test inventory reservations. Security review initData |

**Итого: ~13–14 недель до production-ready MVP**

---

## Ключевые ограничения и инварианты

> [!IMPORTANT]
> Эти правила нельзя нарушать при разработке

1. **Inventory** изменяется только через `inventory_movements` + `SELECT FOR UPDATE`
2. **Order** никогда не меняет `subtotal / total` после создания (snapshot)
3. **prices** — только INSERT новой записи; старая запись получает `valid_to = NOW()`
4. **outbox_events** записываются в той же транзакции что и бизнес-событие
5. **webhook_events** — сначала сохранить raw, потом обработать
6. **initData** — валидировать HMAC на сервере; никогда не доверять `initDataUnsafe`
7. **bot_token** — никогда не хранить в plaintext; только зашифрованным
8. **Idempotency-Key** — обязателен для POST /orders и POST /payments/create
9. **shop_order_number** — UNIQUE(shop_id, number), не глобальный
10. **Все денежные суммы** — NUMERIC(12,2), не float; всегда с currency

---

*Architecture Freeze v1 — 2026-10-02*  
*Следующее изменение архитектуры — только через Architecture Decision Record (ADR)*
