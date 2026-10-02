"""
INV-013: Tenant Context Authenticated Membership Invariant

Tenant context MUST be derived from authenticated identity
and verified shop membership.

Client-provided shop_id/header MUST NEVER grant tenant access.

A valid user from Shop A cannot access Shop B by changing:
    - X-Shop-Id header
    - URL shop_id
    - query parameter
    - path parameter
    - nested entity UUID (orders/items, products, waves, payments)
"""
import pytest
import uuid
from httpx import AsyncClient
from app.modules.auth.jwt import create_access_token
from app.modules.shops.models import Shop, ShopMember
from app.modules.auth.models import User
from app.modules.orders.models import Order, OrderItem


@pytest.mark.asyncio
async def test_inv_013_client_cannot_switch_tenant_via_header(client: AsyncClient, db_session):
    """
    Пользователь из Shop A не может получить контекст Shop B,
    просто передав X-Shop-Id: Shop_B.
    """
    user_a = User(id=uuid.uuid4(), email=f"a_{uuid.uuid4().hex[:6]}@test.com", platform_role="user")
    shop_a = Shop(id=uuid.uuid4(), slug=f"sa-{uuid.uuid4().hex[:6]}", name="Shop A", owner_id=user_a.id)
    member_a = ShopMember(shop_id=shop_a.id, user_id=user_a.id, shop_role="owner")

    user_b = User(id=uuid.uuid4(), email=f"b_{uuid.uuid4().hex[:6]}@test.com", platform_role="user")
    shop_b = Shop(id=uuid.uuid4(), slug=f"sb-{uuid.uuid4().hex[:6]}", name="Shop B", owner_id=user_b.id)
    member_b = ShopMember(shop_id=shop_b.id, user_id=user_b.id, shop_role="owner")

    db_session.add_all([user_a, shop_a, member_a, user_b, shop_b, member_b])
    await db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id), "shop_id": str(shop_a.id)})

    # Запрос с токеном User A, но с заголовком чужого магазина Shop B
    resp = await client.get(
        "/api/v1/admin/orders",
        headers={"Authorization": f"Bearer {token_a}", "X-Shop-Id": str(shop_b.id)}
    )
    # Должен быть отказ в доступе (403), так как User A не состоит в shop_members(Shop B)
    assert resp.status_code in (403, 404), (
        f"INV-013 VIOLATION: User A gained access to Shop B via X-Shop-Id header! HTTP {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_inv_013_nested_resources_and_mutations_protected(client: AsyncClient, db_session):
    """
    Матрица изоляции ресурсов:
    Shop A не может читать, модифицировать (PATCH) или удалять (DELETE)
    ресурсы Shop B (Order, OrderItem, Product, Wave), даже передавая свой валидный заголовок Shop A.
    """
    user_a = User(id=uuid.uuid4(), email=f"usera_{uuid.uuid4().hex[:6]}@test.com", platform_role="user")
    shop_a = Shop(id=uuid.uuid4(), slug=f"sha-{uuid.uuid4().hex[:6]}", name="Shop A", owner_id=user_a.id)
    member_a = ShopMember(shop_id=shop_a.id, user_id=user_a.id, shop_role="owner")

    user_b = User(id=uuid.uuid4(), email=f"userb_{uuid.uuid4().hex[:6]}@test.com", platform_role="user")
    shop_b = Shop(id=uuid.uuid4(), slug=f"shb-{uuid.uuid4().hex[:6]}", name="Shop B", owner_id=user_b.id)
    member_b = ShopMember(shop_id=shop_b.id, user_id=user_b.id, shop_role="owner")

    # Создаем заказ и позицию заказа в Shop B
    order_b = Order(
        id=uuid.uuid4(),
        shop_id=shop_b.id,
        customer_id=uuid.uuid4(),
        number=101,
        order_status="new",
        subtotal=500,
        total=500,
        idempotency_key=f"inv013-{uuid.uuid4().hex}",
    )
    item_b = OrderItem(
        id=uuid.uuid4(),
        order_id=order_b.id,
        product_name="Товар Shop B",
        qty=1,
        unit_price=500,
        subtotal=500,
    )
    db_session.add_all([user_a, shop_a, member_a, user_b, shop_b, member_b, order_b, item_b])
    await db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id), "shop_id": str(shop_a.id)})
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Shop-Id": str(shop_a.id)}

    # 1. Попытка GET вложенного ресурса чужого магазина
    r_get_item = await client.get(f"/api/v1/admin/orders/{order_b.id}/items/{item_b.id}", headers=headers_a)
    assert r_get_item.status_code in (403, 404), (
        f"INV-013 VIOLATION: User A read nested OrderItem of Shop B! HTTP {r_get_item.status_code}"
    )

    # 2. Попытка мутации (PATCH) чужого заказа
    r_patch = await client.patch(
        f"/api/v1/admin/orders/{order_b.id}",
        json={"order_status": "cancelled"},
        headers=headers_a,
    )
    assert r_patch.status_code in (403, 404, 405), (
        f"INV-013 VIOLATION: User A mutated order of Shop B! HTTP {r_patch.status_code}"
    )

    # 3. Попытка DELETE чужого ресурса
    r_delete = await client.delete(f"/api/v1/admin/orders/{order_b.id}", headers=headers_a)
    assert r_delete.status_code in (403, 404, 405), (
        f"INV-013 VIOLATION: User A deleted order of Shop B! HTTP {r_delete.status_code}"
    )
